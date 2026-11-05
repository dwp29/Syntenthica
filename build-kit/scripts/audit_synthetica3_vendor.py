#!/usr/bin/env python3
"""Compare an extracted vendor module directory with a verified 3.0 bundle.

Host-only, read-only inputs. The detailed report is private and must be written
outside this repository and outside every input tree. This is static evidence,
not a module loader, installer, ROM modifier, or device-compatibility verdict.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shlex
import stat
import struct
import sys
import tempfile
from pathlib import Path, PurePosixPath

import build_synthetica3 as build
import verify_synthetica3_modules as verify

REPO = Path(__file__).resolve().parents[2]
MAX_INPUT = 32 * 1024 * 1024
MAX_TEXT = 8 * 1024 * 1024
MODULE_NAME = re.compile(r"[A-Za-z0-9_+.-]+\.ko\Z")
PARAM_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
IGNORE_DEFINITIONS = {"__this_module", "init_module", "cleanup_module"}
IGNORE_PREFIXES = ("__mod_", "__tracepoint_", "__traceiter_", "__SCT__", "__kstrtab_",
                   "__ksymtab_", "__crc_", "__param_")


def read_regular(path: Path, maximum: int = MAX_INPUT) -> bytes:
    """Read a bounded regular file without following the final symlink."""
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > maximum:
            raise ValueError(f"not a bounded regular file: {path}")
        data = stream.read(maximum + 1)
    if len(data) != meta.st_size or len(data) > maximum:
        raise ValueError(f"input changed or was too large: {path}")
    return data


def module_basename(value: str) -> str:
    # Paths from modules.dep are metadata, never filesystem paths to open.
    if "\\" in value or "\x00" in value:
        raise ValueError("unsafe module path")
    path = PurePosixPath(value)
    if ".." in path.parts or not MODULE_NAME.fullmatch(path.name):
        raise ValueError(f"unsupported module path: {value}")
    return path.name


def canonical(name: str) -> str:
    return name.removesuffix(".ko").replace("-", "_")


class ModuleELF:
    """Small bounded parser for the symbol and parameter evidence in an arm64 .ko."""

    def __init__(self, payload: bytes):
        # Reuse the same AArch64/ET_REL, section-bounds and MODVERSIONS checks as
        # the build verifier. Never trust ELF section offsets before this check.
        self.sections = verify.elf_sections(payload)
        self.payload = payload
        h = struct.unpack_from("<16sHHIQQQIHHHHHH", payload)
        shoff, count, strings_index = h[6], h[12], h[13]
        self.rows = [struct.unpack_from("<IIQQQQIIQQ", payload, shoff + 64 * i)
                     for i in range(count)]
        strings = self.section_bytes(strings_index)
        self.names = [self.cstring(strings, row[0]) for row in self.rows]
        tables = [i for i, row in enumerate(self.rows) if row[1] == 2]
        if len(tables) != 1:
            raise ValueError("missing or ambiguous ELF symbol table")
        self.sym_index = tables[0]
        row = self.rows[self.sym_index]
        if row[9] != 24 or row[5] % 24 or row[6] >= len(self.rows) or self.rows[row[6]][1] != 3:
            raise ValueError("invalid ELF symbol table")
        names = self.section_bytes(row[6])
        raw = self.section_bytes(self.sym_index)
        self.symbols = []
        for offset in range(0, len(raw), 24):
            noff, info, other, section, value, size = struct.unpack_from("<IBBHQQ", raw, offset)
            name = self.cstring(names, noff)
            if 0 < section < 0xff00 and section >= len(self.rows):
                raise ValueError("symbol refers to invalid section")
            self.symbols.append((name, info, other, section, value, size))

    @staticmethod
    def cstring(data: bytes, offset: int) -> str:
        if offset >= len(data):
            raise ValueError("ELF string offset out of bounds")
        end = data.find(b"\0", offset)
        if end < 0:
            raise ValueError("unterminated ELF string")
        try:
            return data[offset:end].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("non-ASCII ELF symbol or section name") from exc

    def section_bytes(self, index: int) -> bytes:
        if index >= len(self.rows):
            raise ValueError("ELF section index out of bounds")
        row = self.rows[index]
        if row[1] == 8 or row[4] + row[5] > len(self.payload):
            raise ValueError("invalid ELF data section")
        return self.payload[row[4]:row[4] + row[5]]

    def defined_and_exported(self) -> tuple[set[str], set[str]]:
        defined, exports = set(), set()
        for name, info, _, section, _, _ in self.symbols:
            if name.startswith("__ksymtab_") and section not in (0, 0xfff2):
                exports.add(name[len("__ksymtab_"):])
            if (section != 0 and section < 0xff00 and info >> 4 in (1, 2)
                    and info & 0xf in (1, 2) and name and name not in IGNORE_DEFINITIONS
                    and not name.startswith(IGNORE_PREFIXES)):
                defined.add(name)
        return defined, exports

    def registered_parameters(self) -> set[str]:
        """Find registered 4.14 arm64 parameters, including module_param_cb.

        Descriptive .modinfo/parmtype can omit callbacks. Require a bounded
        __param object, its exact NUL-terminated name, and the AArch64 ABS64
        relocation connecting them. Presence does not establish runtime behavior.
        """
        indexes = [i for i, name in enumerate(self.names) if name == "__param"]
        if not indexes:
            return set()
        if len(indexes) != 1:
            raise ValueError("ambiguous __param section")
        section = indexes[0]
        size = self.rows[section][5]
        if self.rows[section][1] != 1 or size % 40:
            raise ValueError("unexpected arm64 4.14 __param section layout")
        params = {}
        strings = {}
        for symbol in self.symbols:
            name, info, _, shndx, value, length = symbol
            if name.startswith("__param_str_"):
                key = name[len("__param_str_"):]
                if key in strings:
                    raise ValueError("duplicate module parameter string")
                strings[key] = symbol
            elif name.startswith("__param_") and shndx == section:
                key = name[len("__param_"):]
                if key in params or not PARAM_NAME.fullmatch(key) or info & 0xf != 1 or length != 40:
                    raise ValueError("invalid module parameter object")
                if value % 8 or value + length > size:
                    raise ValueError("module parameter object out of bounds")
                params[key] = symbol
        if sorted(s[4] for s in params.values()) != list(range(0, size, 40)):
            raise ValueError("incomplete or overlapping module parameter symbols")

        relocs = {}
        for index, row in enumerate(self.rows):
            if row[1] != 4 or row[7] != section:  # SHT_RELA, sh_info == target
                continue
            if row[6] != self.sym_index or row[9] != 24 or row[5] % 24:
                raise ValueError("invalid __param relocation section")
            raw = self.section_bytes(index)
            for off in range(0, len(raw), 24):
                target, info, addend = struct.unpack_from("<QQq", raw, off)
                if target in relocs:
                    raise ValueError("duplicate __param relocation offset")
                relocs[target] = (info >> 32, info & 0xffffffff, addend)

        for key, obj in params.items():
            string = strings.get(key)
            if string is None:
                raise ValueError("missing parameter name symbol")
            _, info, _, shndx, value, length = string
            if (info & 0xf != 1 or not 0 < shndx < len(self.rows)
                    or value + length > self.rows[shndx][5]):
                raise ValueError("invalid parameter name symbol")
            expected = key.encode("ascii") + b"\0"
            if length != len(expected) or self.section_bytes(shndx)[value:value + length] != expected:
                raise ValueError("parameter name does not match symbol")
            reloc = relocs.get(obj[4])
            if not reloc or reloc[1] != 257 or reloc[0] >= len(self.symbols):  # R_AARCH64_ABS64
                raise ValueError("missing parameter-name relocation")
            target = self.symbols[reloc[0]]
            if target[3] != shndx or target[4] + reloc[2] != value:
                raise ValueError("parameter relocation targets a different string")
        return set(params)


def verify_manifest(bundle: Path) -> None:
    required = {"DO-NOT-FLASH-Synthetica-3.0-Image.gz", "Module.symvers.txt", "System.map.txt",
                "generated.config.txt", "STATUS.json", "kernel-module-public-cert.x509"}
    required.update(f"signed-modules/{name}.ko" for name in verify.MODULE_CONFIG)
    text = read_regular(bundle / "SHA256SUMS.txt", MAX_TEXT).decode("ascii")
    seen = set()
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (\S+)", line)
        if not match:
            raise ValueError("invalid bundle checksum entry")
        expected, name = match.groups()
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts or name in seen:
            raise ValueError("unsafe or duplicate checksum entry")
        seen.add(name)
        data = read_regular(bundle.joinpath(*p.parts))
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"bundle checksum mismatch: {name}")
    if not required <= seen:
        raise ValueError("bundle checksum manifest is incomplete")


def load_bundle(bundle: Path) -> dict:
    verify_manifest(bundle)
    status = json.loads(read_regular(bundle / "STATUS.json", MAX_TEXT))
    if status.get("status") != "COMPILED_ONLY_DO_NOT_FLASH":
        raise ValueError("bundle must be marked not flashable")
    release = status.get("uname_release")
    if not isinstance(release, str) or not release:
        raise ValueError("bundle release is missing")
    config = build.read_config(read_regular(bundle / "generated.config.txt", MAX_TEXT).decode("utf-8"))
    cert = read_regular(bundle / "kernel-module-public-cert.x509", MAX_TEXT)
    image = read_regular(bundle / "DO-NOT-FLASH-Synthetica-3.0-Image.gz")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(image)) as compressed:
            raw = compressed.read(build.MAX_RAW_IMAGE + 1)
    except (OSError, EOFError) as exc:
        raise ValueError("invalid bundle kernel gzip") from exc
    if len(raw) > build.MAX_RAW_IMAGE or raw.count(cert) != 1:
        raise ValueError("bundle kernel does not contain exactly one build certificate")
    symvers_text = read_regular(bundle / "Module.symvers.txt", MAX_TEXT).decode("ascii")
    symvers = verify.symvers_records(symvers_text)
    evidence = verify.collect(bundle / "signed-modules", config=config, release=release,
                              certificate_der=cert, raw_kernel=raw, symvers_text=symvers_text)
    parameters = {}
    for name, (data, _) in evidence.items():
        payload, _ = verify.split_signature(data)
        parameters[name] = ModuleELF(payload).registered_parameters()
    builtins = set()
    for line in symvers_text.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[2] == "vmlinux":
            builtins.add(fields[1])
    map_names = set()
    for line in read_regular(bundle / "System.map.txt", MAX_TEXT).decode("ascii").splitlines():
        fields = line.split()
        if len(fields) != 3 or not re.fullmatch(r"[0-9a-fA-F]+", fields[0]) or len(fields[1]) != 1:
            raise ValueError("invalid System.map entry")
        map_names.add(fields[2])
    return {"release": release, "config": config, "cert": cert, "symvers": symvers,
            "builtins": builtins, "map_names": map_names, "parameters": parameters}


def read_lists(directory: Path) -> tuple[list[str], dict[str, list[str]]]:
    load = []
    for line in read_regular(directory / "modules.load", MAX_TEXT).decode("utf-8").splitlines():
        line = line.partition("#")[0].strip()
        if line:
            if len(line.split()) != 1:
                raise ValueError("invalid modules.load line")
            load.append(module_basename(line))
    if not load or len(load) != len(set(load)):
        raise ValueError("empty or duplicate modules.load entries")
    deps = {}
    for line in read_regular(directory / "modules.dep", MAX_TEXT).decode("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        left, sep, right = line.partition(":")
        if not sep or ":" in right:
            raise ValueError("invalid modules.dep line")
        name = module_basename(left.strip())
        if name in deps:
            raise ValueError("duplicate modules.dep entry")
        deps[name] = [module_basename(x) for x in right.split()]
    return load, deps


def audit_one(path: Path, target: dict, loaded: bool) -> dict:
    data = read_regular(path)
    if data.endswith(verify.SIG_MAGIC):
        payload, signature = verify.split_signature(data)
        try:
            verify.verify_pkcs7(payload, signature, target["cert"])
            signature_result = "verified_with_bundle_certificate"
        except ValueError:
            signature_result = "not_verified_with_bundle_certificate"
    else:
        payload, signature_result = data, "no_appended_signature"
    elf = ModuleELF(payload)
    info = verify.module_info(elf.sections[".modinfo"])
    versions = verify.version_records(elf.sections["__versions"])
    defined, exports = elf.defined_and_exported()
    symvers = target["symvers"]
    return {
        "file": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "listed_in_modules_load": loaded,
        "internal_name": info["name"],
        "modinfo_dependencies": [x for x in info.get("depends", "").split(",") if x],
        "vermagic": info["vermagic"],
        "signature_result": signature_result,
        "module_layout_crc": f"0x{versions['module_layout']:08x}",
        "module_layout_matches_bundle": versions["module_layout"] == symvers["module_layout"],
        "version_records": {
            "matched": sum(symvers.get(name) == crc for name, crc in versions.items()),
            "different": sum(name in symvers and symvers[name] != crc for name, crc in versions.items()),
            "absent_from_bundle": sum(name not in symvers for name in versions),
        },
        "defined_symbol_names": len(defined),
        "defined_names_in_target_system_map": len(defined & target["map_names"]),
        "exported_symbol_names": len(exports),
        "export_names_in_target_vmlinux": len(exports & target["builtins"]),
    }


def source_index(source: Path, config: dict[str, str]) -> dict[str, list[dict]]:
    """Index simple Kbuild object assignments; variables/conditionals are not evaluated."""
    auto_path = source / "techpack/audio/4.0/config/atollauto.conf"
    auto = {}
    if auto_path.is_file() and not auto_path.is_symlink():
        for line in read_regular(auto_path, MAX_TEXT).decode("utf-8").splitlines():
            match = re.fullmatch(r"CONFIG_([A-Za-z0-9_]+)=(.*)", line.strip())
            if match:
                auto[match.group(1)] = match.group(2)
    result = {}
    files_seen = 0
    for root, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(root) / d).is_symlink() and d != ".git")
        for filename in sorted(files):
            if filename not in ("Kbuild", "Makefile"):
                continue
            path = Path(root) / filename
            if path.is_symlink():
                continue
            files_seen += 1
            if files_seen > 50000:
                raise ValueError("too many source build files")
            text = read_regular(path, MAX_TEXT).decode("utf-8", "replace")
            mods = set(re.findall(r"(?m)^\s*MODNAME\s*[:?]?=\s*([\w-]+)\s*$", text))
            for line in text.splitlines():
                match = re.match(r"^\s*obj-\$\(CONFIG_([A-Za-z0-9_]+)\)\s*\+?=\s*(.*)", line)
                if not match:
                    continue
                key, rhs = match.groups()
                objects = re.findall(r"([A-Za-z0-9_-]+)\.o\b", rhs)
                if "$(MODNAME).o" in rhs and len(mods) == 1:
                    objects.extend(mods)
                for obj in objects:
                    item = {"file": str(path.relative_to(source)), "config": key,
                            "generated_config": config.get(key, "not present"),
                            "atoll_auto_config": auto.get(key, "not present")}
                    bucket = result.setdefault(canonical(obj), [])
                    if item not in bucket:
                        bucket.append(item)
    return result


def init_commands(directory: Path, bundle_params: dict[str, set[str]]) -> tuple[list[dict], list[dict]]:
    """Parse common literal init insmod/modprobe lines, not shell expansions."""
    commands, unparsed = [], []
    paths = sorted(directory.rglob("*.rc"))
    if len(paths) > 5000:
        raise ValueError("too many init files")
    for path in paths:
        if path.is_symlink():
            raise ValueError("symlink in init inputs")
        current = None
        text = read_regular(path, MAX_TEXT).decode("utf-8", "replace")
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("on ") and not line[:1].isspace():
                current = stripped[3:]
                continue
            if stripped.startswith("service ") and not line[:1].isspace():
                current = None
                continue
            if not current or not line[:1].isspace() or not re.search(r"\b(?:insmod|modprobe)\b", stripped):
                continue
            location = {"file": str(path.relative_to(directory)), "line": number, "trigger": current}
            try:
                words = shlex.split(stripped, comments=True, posix=True)
                if not words:
                    continue
                if words[0] == "insmod" and len(words) >= 2:
                    operation = "insmod"
                    args = words[1:]
                elif words[0] in ("exec", "exec_background") and "--" in words:
                    args = words[words.index("--") + 1:]
                    if not args or PurePosixPath(args[0]).name != "modprobe":
                        continue
                    operation, args = "modprobe", args[1:]
                else:
                    continue
                names, options, params, search_dirs = [], [], [], []
                idx = 0
                while idx < len(args):
                    arg = args[idx]
                    if operation == "modprobe" and arg == "-d":
                        idx += 1
                        if idx >= len(args):
                            raise ValueError("missing -d value")
                        search_dirs.append(args[idx])
                    elif operation == "modprobe" and arg.startswith("-"):
                        if not re.fullmatch(r"-[alrqvsDb]+", arg):
                            raise ValueError("unsupported modprobe option")
                        options.append(arg)
                    elif "=" in arg:
                        key = arg.partition("=")[0].replace("-", "_")
                        if not PARAM_NAME.fullmatch(key):
                            raise ValueError("nonliteral parameter")
                        params.append(key)
                    elif re.fullmatch(r"[A-Za-z0-9_./+-]+", arg) and ".." not in PurePosixPath(arg).parts:
                        names.append(canonical(PurePosixPath(arg).name))
                    else:
                        raise ValueError("nonliteral module name")
                    idx += 1
                if not names:
                    raise ValueError("no literal module target")
                comparisons = []
                for name in names:
                    if name in bundle_params:
                        missing = sorted(set(params) - bundle_params[name])
                        comparisons.append({"bundle_module": name, "parameter_names": sorted(set(params)),
                                            "not_found_in_bundle_parameters": missing})
                commands.append({**location, "operation": operation, "search_dirs": search_dirs,
                                 "remove_requested": any("r" in x[1:] for x in options),
                                 "modules": names, "bundle_parameter_comparisons": comparisons})
            except ValueError as exc:
                unparsed.append({**location, "reason": str(exc)})
    return commands, unparsed


def unresolved_cycles(dependencies: dict[str, list[str]], names: set[str]) -> list[str]:
    # Nodes that remain either belong to, or depend on, a cycle. Missing files
    # and missing dep entries are reported separately, not inferred as cycles.
    pending = {name: set(deps) & names for name, deps in dependencies.items() if name in names}
    while pending:
        ready = {name for name, deps in pending.items() if not deps.intersection(pending)}
        if not ready:
            break
        for name in ready:
            del pending[name]
    return sorted(pending)


def audit(module_dir: Path, bundle_dir: Path, init_dir: Path | None = None,
          source_dir: Path | None = None) -> dict:
    target = load_bundle(bundle_dir)
    load, dependencies = read_lists(module_dir)
    paths = sorted(module_dir.glob("*.ko"))
    if not paths or len(paths) > 1000 or len({p.name for p in paths}) != len(paths):
        raise ValueError("invalid module directory")
    names = {path.name for path in paths}
    missing = sorted(set(load) - names)
    if missing:
        raise ValueError("modules.load references missing files")
    positions = {name: index for index, name in enumerate(load)}
    rows = [audit_one(path, target, path.name in positions) for path in paths]
    index = source_index(source_dir, target["config"]) if source_dir else {}
    for row in rows:
        file = row["file"]
        row["dependencies"] = dependencies.get(file)
        candidates = index.get(canonical(row["internal_name"]), []) + index.get(canonical(file), [])
        row["source_kbuild_candidates"] = list({json.dumps(x, sort_keys=True): x for x in candidates}.values())
    late = [{"module": name, "dependency": dep} for name, deps in dependencies.items() if name in positions
            for dep in deps if dep in positions and positions[dep] > positions[name]]
    missing_deps = sorted({dep for deps in dependencies.values() for dep in deps if dep not in names})
    cycles = unresolved_cycles(dependencies, names)
    commands, unparsed = init_commands(init_dir, target["parameters"]) if init_dir else ([], [])
    inventory = []
    for name in sorted(target["parameters"]):
        inventory.append({
            "bundle_module": name,
            "same_name_file_in_extracted_directory": any(canonical(x) == name for x in names),
            "same_name_in_extracted_modules_dep": any(canonical(x) == name for x in dependencies),
            "referenced_in_literal_init_commands": any(name in command["modules"] for command in commands),
        })
    return {
        "scope": "Static host-only comparison; not a load, boot, trust-store, device, or feature test.",
        "warning": "Private ROM-derived metadata. Keep this report outside repositories and uploads.",
        "target_release": target["release"],
        "target_certificate_sha256": hashlib.sha256(target["cert"]).hexdigest(),
        "modules": rows,
        "modules_load_count": len(load),
        "dependency_entries_missing_for_loaded": sorted(set(load) - set(dependencies)),
        "dependency_entries_missing_for_all_modules": sorted(names - set(dependencies)),
        "dependency_files_missing": missing_deps,
        "dependencies_later_in_load_list": late,
        "modules_in_or_depending_on_cycles": cycles,
        "bundle_module_inventory": inventory,
        "init_commands": commands,
        "unparsed_init_commands": unparsed,
        "init_note": "Only literal .rc insmod/modprobe commands in the supplied tree are inspected; execution and other search directories are unknown.",
        "source_note": "Kbuild matches are candidates only; source identity and conditionals are not verified.",
    }


def validate_output(path: Path, protected: list[Path]) -> Path:
    if not path.is_absolute() or not path.name:
        raise ValueError("report path must be absolute")
    parent = path.parent.resolve(strict=True)
    for root in [REPO, *protected]:
        resolved = root.resolve(strict=True)
        if parent == resolved or resolved in parent.parents:
            raise ValueError("report must be outside the repository and every input tree")
    destination = parent / path.name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"report already exists: {destination}")
    return destination


def write_private(path: Path, report: dict, protected: list[Path]) -> None:
    destination = validate_output(path, protected)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True)
            output.write("\n")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules", required=True, type=Path, help="private extracted vendor/lib/modules directory")
    parser.add_argument("--bundle", required=True, type=Path, help="same-build, non-flashable 3.0 bundle directory")
    parser.add_argument("--init", type=Path, help="optional private extracted vendor/etc/init tree")
    parser.add_argument("--source", type=Path, help="optional independently verified 2.0 kernel source tree")
    parser.add_argument("--output", required=True, type=Path, help="new absolute report path outside repository/inputs")
    args = parser.parse_args()
    protected = [x for x in (args.modules, args.bundle, args.init, args.source) if x is not None]
    try:
        for root in protected:
            if not root.is_dir() or root.is_symlink():
                raise ValueError(f"input is not a nonsymlink directory: {root}")
        destination = validate_output(args.output, protected)
        # The shared signature verifier uses tempfile. Keep its transient module
        # payloads in a private directory next to the report, even if TMPDIR is
        # set to the repository or an input tree. This CLI is single-threaded.
        with tempfile.TemporaryDirectory(prefix=".synthetica3-audit-", dir=destination.parent) as scratch:
            previous_tempdir = tempfile.tempdir
            try:
                tempfile.tempdir = scratch
                report = audit(args.modules, args.bundle, args.init, args.source)
            finally:
                tempfile.tempdir = previous_tempdir
        write_private(args.output, report, protected)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"Audit did not complete: {exc}", file=sys.stderr)
        return 1
    print(f"Static audit completed for {len(report['modules'])} modules. Private report: {args.output}")
    print("Not a compatibility or boot test; do not flash.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
