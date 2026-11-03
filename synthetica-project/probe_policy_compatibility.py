#!/usr/bin/env python3
"""Test existing split SELinux policy and a VINTF hypothesis, never alter an image.

Only a hash-verified, disposable copy of candidate 02 is read; candidate 03 has
exactly the same super.img. Extracted policy inputs live on a disposable runner
and are read by a pinned AOSP host secilc inside a networkless, read-only
namespace. Strict compilation keeps neverallow checks enabled. A separate,
clearly-labelled comparison models the cited AOSP init compiler invocation:
its -N flag skips compile-time neverallow assertions, not device enforcement.
Only the sandbox's throwaway output is produced; it is never packaged. A
one-field VINTF hypothesis is tried ONLY on a temporary snapshot, restored,
and never packaged. None of these tests proves device boot. No candidate init
JSON, raw policy content, or compiled candidate policy is exported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import audit_checkvintf_snapshot as check
import audit_guarded_zip64_draft as draft
import audit_updater_emulation as emu
import audit_vintf_candidate as inventory
import audit_vndk_candidates as vndk
import audit_vndk_apex as vndk_apex
import audit_apex_avb_verify as avb_verify
import audit_vndk_symbols as vndk_symbols
import audit_vendor_abi as vendor_abi
import audit_vendor_elf_metadata as vendor_elf

ROOT = Path(__file__).resolve().parents[1]
MAX_CIL = 16 * 1024 * 1024
MAX_TOOL = 64 * 1024 * 1024
MAX_LOG = 1024 * 1024
VERSION = '31.0'  # Actual vendor mapping file previously read, not VINTF version.
MANIFEST = 'vendor/etc/vintf/manifest.xml'

# Fixed and deliberately narrow snapshot. True means required for this test;
# optional files from an actual separately mounted ODM are not available here.
FILES = (
    ('system', '/system/etc/selinux/plat_sepolicy.cil', 'system.cil', True,
     '8be91bf28cbefad3fc4bf556f5baa6de3d027a8cd86247b9317411b056b1e6df'),
    ('system', '/system/etc/selinux/mapping/31.0.cil', 'system_mapping.cil', True, None),
    ('system', '/system/etc/selinux/mapping/31.0.compat.cil', 'system_compat.cil', False, None),
    ('system', '/system/etc/selinux/plat_sepolicy_genfs_0.cil', 'genfs0.cil', False, None),
    ('system_ext', '/etc/selinux/system_ext_sepolicy.cil', 'system_ext.cil', False,
     'f0b5e3687b0cb29f9fa44773b29a0af3c397c923e0a22bbc6af559018303f30a'),
    ('system_ext', '/etc/selinux/mapping/31.0.cil', 'system_ext_mapping.cil', False, None),
    ('system_ext', '/etc/selinux/mapping/31.0.compat.cil', 'system_ext_compat.cil', False, None),
    ('product', '/etc/selinux/product_sepolicy.cil', 'product.cil', False,
     '103ee85629eb8caaa75820420e888a19bf6617a436014bb41caec2c2243b3f42'),
    ('product', '/etc/selinux/mapping/31.0.cil', 'product_mapping.cil', False, None),
    ('vendor', '/etc/selinux/plat_pub_versioned.cil', 'vendor_public.cil', True,
     '9d20d41a2b4b39063a3b611e582151a61948d644bb9e712144256c6873ce393c'),
    ('vendor', '/etc/selinux/vendor_sepolicy.cil', 'vendor.cil', True,
     'dcac865cc11c4a7d5bd5f4017f4df23dcbdf36f2723056f104b7f3e870d527fb'),
    ('vendor', '/odm/etc/selinux/odm_sepolicy.cil', 'odm_in_vendor.cil', False, None),
)
ORDER = ('system.cil', 'system_mapping.cil', 'system_compat.cil',
         'system_ext.cil', 'system_ext_mapping.cil', 'system_ext_compat.cil',
         'product.cil', 'product_mapping.cil', 'vendor_public.cil', 'vendor.cil',
         'odm_in_vendor.cil', 'genfs0.cil')

# AOSP external/selinux secilc/test/minimum.cil, commit 6f8f496eabd35f28dfa6b4be5fc82e325e1df620.
MINIMUM_CIL = b'''(class CLASS (PERM))
(classorder (CLASS))
(sid SID)
(sidorder (SID))
(user USER)
(role ROLE)
(type TYPE)
(category CAT)
(categoryorder (CAT))
(sensitivity SENS)
(sensitivityorder (SENS))
(sensitivitycategory SENS (CAT))
(allow TYPE self (CLASS (PERM)))
(roletype ROLE TYPE)
(userrole USER ROLE)
(userlevel USER (SENS))
(userrange USER ((SENS)(SENS (CAT))))
(sidcontext SID (USER ROLE TYPE ((SENS)(SENS))))
'''


class PolicyProbeError(RuntimeError):
    pass


def prepare_secilc(archive: Path, sandbox: Path) -> dict:
    # This verifies the whole public Android CI otatools ZIP, installs a pinned
    # checkvintf for VINTF controls, and copies its bounded host runtime libs.
    tool = check.prepare_tool(archive, sandbox)
    target = sandbox / 'tool/secilc'
    with zipfile.ZipFile(archive) as z:
        matches = [i for i in z.infolist() if i.filename == 'bin/secilc']
        if len(matches) != 1:
            raise PolicyProbeError('AOSP secilc entry missing or duplicated')
        info = matches[0]
        if (info.is_dir() or info.flag_bits & 1 or not 0 < info.file_size <= MAX_TOOL
                or stat.S_ISLNK(info.external_attr >> 16)):
            raise PolicyProbeError('Unsafe secilc archive entry')
        with z.open(info) as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
    target.chmod(0o555)
    elf = subprocess.run(['readelf', '-d', str(target)], capture_output=True, text=True, check=True)
    needed = set(re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', elf.stdout))
    if not needed.issubset(set(check.HOST_LIBS)):
        raise PolicyProbeError('Unexpected AOSP secilc runtime dependencies')
    (sandbox / 'out').mkdir()
    (sandbox / 'policy').mkdir()
    return {**tool, 'secilc_sha256': check.sha256_file(target),
            'secilc_bytes': target.stat().st_size, 'secilc_needed': sorted(needed),
            'secilc_source': 'bin/secilc within the SHA-256 pinned otatools ZIP',
            'strict_compiler_neverallow_checks_disabled': False,
            'reference_compilation_is_diagnostic_only': True}


def write_policy_file(directory: Path, name: str, data: bytes) -> None:
    if not re.fullmatch(r'[a-z0-9_]+\.cil', name) or not data or len(data) > MAX_CIL:
        raise PolicyProbeError('Unsafe or oversized CIL input')
    dest = directory / name
    if dest.exists() or dest.is_symlink():
        raise PolicyProbeError('Duplicate snapshot policy name')
    with dest.open('xb') as out:
        out.write(data)
    dest.chmod(0o444)


def read_vendor_mapping_version(fs) -> dict:
    path = '/etc/selinux/plat_sepolicy_vers.txt'
    try:
        entry = fs.open(path=path)
    except (OSError, RuntimeError) as exc:
        raise PolicyProbeError('Vendor mapping-version file is unavailable') from exc
    meta = entry.info.meta
    if (meta is None or not (meta.flags & inventory.pytsk3.TSK_FS_META_FLAG_ALLOC)
            or meta.type != inventory.pytsk3.TSK_FS_META_TYPE_REG or not 0 < int(meta.size) <= 128):
        raise PolicyProbeError('Vendor mapping-version file is not a bounded regular file')
    data = entry.read_random(0, int(meta.size))
    digest = hashlib.sha256(data).hexdigest()
    if (len(data) != int(meta.size) or data.strip() != VERSION.encode('ascii')
            or digest != 'c1be93ff1e96d84c1d4f3cffbaa3654adfe996bb2c8263733d4f6aabed72b37f'):
        raise PolicyProbeError('Vendor mapping-version differs from the previously pinned file')
    return {'path': path, 'value': VERSION, 'bytes': len(data), 'sha256': digest}


def capture_partition(image: Path, partition: str, directory: Path, rows: list[dict],
                      mapping_version: dict) -> None:
    if inventory.pytsk3 is None:
        raise PolicyProbeError('The pinned filesystem reader is missing')
    disk = inventory.pytsk3.Img_Info(str(image))
    fs = inventory.pytsk3.FS_Info(disk)
    if fs.info.ftype != inventory.pytsk3.TSK_FS_TYPE_EXT4:
        raise PolicyProbeError('Expected an ext4 partition image')
    if partition == 'vendor':
        mapping_version.update(read_vendor_mapping_version(fs))
    for part, path, name, required, expected in FILES:
        if part != partition:
            continue
        try:
            entry = fs.open(path=path)
        except (OSError, RuntimeError):
            if required:
                raise PolicyProbeError(f'Required policy file unavailable: {part}:{path}')
            rows.append({'partition': part, 'name': name, 'status': 'missing_or_unreadable'})
            continue
        meta = entry.info.meta
        if (meta is None or not (meta.flags & inventory.pytsk3.TSK_FS_META_FLAG_ALLOC)
                or meta.type != inventory.pytsk3.TSK_FS_META_TYPE_REG):
            raise PolicyProbeError(f'Policy file is not an allocated regular file: {part}:{path}')
        size = int(meta.size)
        if not 0 < size <= MAX_CIL:
            raise PolicyProbeError(f'Policy file is empty or too large: {part}:{path}')
        data = bytearray()
        while len(data) < size:
            block = entry.read_random(len(data), min(1024 * 1024, size - len(data)))
            if not block or len(block) > size - len(data):
                raise PolicyProbeError('Short policy filesystem read')
            data.extend(block)
        digest = hashlib.sha256(data).hexdigest()
        if expected is not None and digest != expected:
            raise PolicyProbeError(f'Previously pinned policy SHA-256 differs: {part}:{path}')
        write_policy_file(directory, name, bytes(data))
        rows.append({'partition': part, 'name': name, 'status': 'read', 'bytes': size, 'sha256': digest})


def candidate_args(rows: list[dict]) -> list[str]:
    found = {r['name'] for r in rows if r['status'] == 'read'}
    required = {name for _, _, name, is_required, _ in FILES if is_required}
    if not required.issubset(found) or not found.issubset(set(ORDER)):
        raise PolicyProbeError('Incomplete or unexpected policy snapshot')
    # AOSP Android 17 init uses policydb version 30 and these input files.
    # This strict gate deliberately does not use init's -N, so all
    # neverallow assertions are checked; the separate reference run is labelled.
    inputs = ['/policy/' + name for name in ORDER if name in found]
    return [inputs[0], '-m', '-M', 'true', '-G', '-c', '30',
            *inputs[1:], '-o', '/out/policy.bin', '-f', '/out/file_contexts']


_LAUNCHER = r'''
import ctypes, hashlib, json, os, re, resource, signal, subprocess, sys
root, mode, *args = sys.argv[1:]
strict = mode in ('control', 'candidate')
reference_inputs = {'reference_control': '/policy/control_neverallow.cil',
                    'reference_unknown': '/policy/control_unknown.cil',
                    'reference_candidate': '/policy/system.cil'}
reference = mode in reference_inputs
if not (strict or reference) or (strict and '-N' in args) or (reference and args.count('-N') != 1):
    raise RuntimeError('invalid mode or compiler assertion-check setting')
if reference and (not args or args[0] != reference_inputs[mode]):
    raise RuntimeError('reference compiler input is not the fixed snapshot')
subprocess.run(['/usr/bin/mount', '--make-rprivate', '/'], check=True)
subprocess.run(['/usr/bin/mount', '--bind', root, root], check=True)
subprocess.run(['/usr/bin/mount', '-o', 'remount,bind,ro', root], check=True)
try:
    fd = os.open(root + '/readonly-marker', os.O_WRONLY)
except OSError:
    pass
else:
    os.close(fd)
    raise RuntimeError('isolated root is not read-only')
subprocess.run(['/usr/bin/mount', '-t', 'tmpfs', '-o',
                'size=128m,nr_inodes=1024,mode=0700,nosuid,nodev,noexec',
                'tmpfs', root + '/out'], check=True)
os.chroot(root)
os.chdir('/')
if any(os.path.exists(x) for x in ('/proc', '/dev', '/home')):
    raise RuntimeError('unexpected host path in isolated root')
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CPU, (100, 100))
resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
libc = ctypes.CDLL(None, use_errno=True)
class Header(ctypes.Structure):
    _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int)]
class Data(ctypes.Structure):
    _fields_ = [('effective', ctypes.c_uint32), ('permitted', ctypes.c_uint32),
                ('inheritable', ctypes.c_uint32)]
header = Header(0x20080522, 0)
if libc.prctl(38, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), 'no_new_privs')
empty = (Data * 2)()
if libc.capset(ctypes.byref(header), ctypes.byref(empty)) != 0:
    raise OSError(ctypes.get_errno(), 'capset')
actual = (Data * 2)()
if libc.capget(ctypes.byref(header), ctypes.byref(actual)) != 0 or any(
        x.effective or x.permitted or x.inheritable for x in actual):
    raise RuntimeError('capabilities were not cleared')
os.closerange(3, 4096)
with open('/out/compiler.log', 'wb') as log:
    # stdin is already the caller's pre-opened /dev/null; there is no /dev in chroot.
    proc = subprocess.run(['/tool/secilc', *args], stdin=None,
                          stdout=log, stderr=log,
                          env={'PATH': '/empty', 'LANG': 'C',
                               'LD_LIBRARY_PATH': '/lib/x86_64-linux-gnu'}, timeout=110)
try:
    os.kill(-1, signal.SIGKILL)
except ProcessLookupError:
    pass
with open('/out/compiler.log', 'rb') as f:
    log = f.read(1024 * 1024 + 1)
if len(log) > 1024 * 1024:
    raise RuntimeError('compiler log exceeded bound')
text = log.decode('utf-8', 'replace')
# Publish diagnostic categories and safe identifiers/locations, never raw CIL,
# init material, paths outside the fixed sandbox, or complete compiler logs.
resolved = re.findall(r'Failed to resolve ([A-Za-z_][A-Za-z0-9_]*) statement', text)
missing = re.findall(r'Failed to (?:resolve|find) (?:permission|class|sid|category|sensitivity) ([A-Za-z_][A-Za-z0-9_.]*)', text)
locations = re.findall(r'at /policy/([a-z0-9_]+\.cil):(\d+)', text)
assertions = re.findall(r'neverallow(?:xperm|x)? check failed at /policy/([a-z0-9_]+\.cil):(\d+)', text, re.I)
allowed_sources = {'system.cil', 'system_mapping.cil', 'system_compat.cil', 'genfs0.cil',
                   'system_ext.cil', 'system_ext_mapping.cil', 'system_ext_compat.cil',
                   'product.cil', 'product_mapping.cil', 'vendor_public.cil', 'vendor.cil',
                   'odm_in_vendor.cil', 'control_neverallow.cil'}
if any(name not in allowed_sources for name, _ in assertions):
    raise RuntimeError('Unexpected policy location in compiler diagnostic')
assertion_counts = {name: sum(1 for item, _ in assertions if item == name)
                    for name in sorted({item for item, _ in assertions})}
policy = '/out/policy.bin'
result = {'tool_exit_code': proc.returncode, 'log_bytes': len(log),
          'log_sha256': hashlib.sha256(log).hexdigest(),
          'failed_resolve_statement_kinds': sorted(set(resolved))[:20],
          'missing_symbol_names': sorted(set(missing))[:20],
          'fixed_policy_file_locations': [{'name': n, 'line': int(i)} for n, i in locations[:20]],
          'neverallow_failure_count': len(assertions),
          'neverallow_failures_by_source': assertion_counts,
          'neverallow_diagnostic': 'neverallow' in text.lower(),
          'unknown_symbol_diagnostic': any(x in text.lower() for x in ('failed to resolve', 'failed to find', 'not declared')),
          'syntax_diagnostic': any(x in text.lower() for x in ('syntax error', 'bad syntax', 'invalid syntax')),
          'root_read_only': True, 'no_network': True, 'no_new_privs': True,
          'capabilities_dropped': True, 'neverallow_checks_disabled': reference,
          'compiled_output_is_disposable_not_shipped': True}

if os.path.isfile(policy):
    with open(policy, 'rb') as f:
        data = f.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024:
        raise RuntimeError('compiled temporary policy exceeds limit')
    result['compiled_policy_bytes'] = len(data)
    result['compiled_policy_sha256'] = hashlib.sha256(data).hexdigest()
if mode in ('control', 'reference_control', 'reference_unknown'):
    result['synthetic_log'] = text[:6000]
print(json.dumps(result), flush=True)
'''


def compile_isolated(sandbox: Path, args: list[str], mode: str) -> dict:
    strict = mode in ('control', 'candidate')
    reference_inputs = {'reference_control': '/policy/control_neverallow.cil',
                        'reference_unknown': '/policy/control_unknown.cil',
                        'reference_candidate': '/policy/system.cil'}
    reference = mode in reference_inputs
    if not (strict or reference) or (strict and '-N' in args) or (reference and args.count('-N') != 1):
        raise PolicyProbeError('Invalid mode or compiler assertion-check setting')
    if reference and (not args or args[0] != reference_inputs[mode]):
        raise PolicyProbeError('Reference compiler input is not the fixed snapshot')
    if not shutil.which('unshare') or not Path('/usr/bin/mount').is_file():
        raise PolicyProbeError('Namespace or mount tools are unavailable')
    command = [shutil.which('unshare'), '--user', '--map-root-user', '--mount', '--net', '--pid', '--fork',
               sys.executable, '-I', '-S', '-c', _LAUNCHER, str(sandbox), mode, *args]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    try:
        out, err = proc.communicate(timeout=130)
    except subprocess.TimeoutExpired as exc:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise PolicyProbeError('Isolated compiler exceeded time limit') from exc
    if len(out) + len(err) > MAX_LOG or proc.returncode:
        # Only fixture failures can show bounded logs. Candidate diagnostics are
        # withheld, not rerouted or re-encoded.
        diagnostic = err.decode('utf-8', 'replace')[:2000] if mode in ('control', 'reference_control', 'reference_unknown') else 'candidate diagnostic withheld'
        raise PolicyProbeError(f'Isolated compiler launcher failed ({proc.returncode}): {diagnostic}')
    try:
        result = json.loads(out)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PolicyProbeError('Invalid isolated compiler result') from exc
    if (result.get('neverallow_checks_disabled') is not reference or not result.get('root_read_only')
            or result.get('compiled_output_is_disposable_not_shipped') is not True):
        raise PolicyProbeError('Compiler isolation or assertion-check guard failed')
    return result


def controls(sandbox: Path) -> list[dict]:
    directory = sandbox / 'policy'
    cases = (
        ('control_good.cil', MINIMUM_CIL, True),
        ('control_unknown.cil', MINIMUM_CIL + b'\n(allow UNDECLARED self (CLASS (PERM)))\n', False),
        ('control_neverallow.cil', MINIMUM_CIL + b'\n(neverallow TYPE self (CLASS (PERM)))\n', False),
    )
    rows = []
    for name, data, should_pass in cases:
        write_policy_file(directory, name, data)
        args = ['/policy/' + name, '-m', '-M', 'true', '-G', '-c', '30',
                '-o', '/out/policy.bin', '-f', '/out/file_contexts']
        result = compile_isolated(sandbox, args, 'control')
        if (result['tool_exit_code'] == 0) != should_pass:
            raise PolicyProbeError(f'Synthetic {name} control yielded an unexpected result: {result}')
        if should_pass and not result.get('compiled_policy_bytes'):
            raise PolicyProbeError('Synthetic positive control did not produce policy')
        if name == 'control_neverallow.cil' and not result['neverallow_diagnostic']:
            raise PolicyProbeError('Synthetic neverallow control failed for the wrong reason')
        rows.append({'case': name, 'tool_exit_code': result['tool_exit_code'],
                     'expected_success': should_pass, 'neverallow_checks_enabled': True})
    return rows


def reference_controls(sandbox: Path) -> dict:
    """Prove the diagnostic-only -N comparison still rejects unresolved symbols.

    The neverallow assertion has no representation in the binary policy. A
    synthetic allowed rule compiled with and without a neverallow assertion
    should produce the same binary when that assertion is skipped. This is
    not an authorization to ignore strict failures on a real candidate.
    """
    def args(name: str, reference: bool) -> list[str]:
        return ['/policy/' + name, '-m', '-M', 'true', '-G', '-c', '30',
                *(['-N'] if reference else []), '-o', '/out/policy.bin', '-f', '/out/file_contexts']
    good = compile_isolated(sandbox, args('control_good.cil', False), 'control')
    skipped = compile_isolated(sandbox, args('control_neverallow.cil', True), 'reference_control')
    unknown = compile_isolated(sandbox, args('control_unknown.cil', True), 'reference_unknown')
    if good['tool_exit_code'] != 0 or skipped['tool_exit_code'] != 0 or unknown['tool_exit_code'] == 0:
        raise PolicyProbeError('Reference-mode synthetic controls produced unexpected results')
    good_hash = good.get('compiled_policy_sha256')
    skip_hash = skipped.get('compiled_policy_sha256')
    if not good_hash or not skip_hash:
        raise PolicyProbeError('Reference-mode positive synthetic controls produced no policy')
    return {'good_strict_exit_code': good['tool_exit_code'],
            'neverallow_assertion_skipped_exit_code': skipped['tool_exit_code'],
            'unknown_symbol_still_rejected_exit_code': unknown['tool_exit_code'],
            'synthetic_binary_identical': good_hash == skip_hash,
            'synthetic_strict_policy_sha256': good_hash,
            'synthetic_reference_policy_sha256': skip_hash,
            'candidate_and_device_policy_modified': False}


def vintf_extended_diagnostics(text: str) -> dict:
    """Relay numeric, specifically-recognized VNDK/SDK diagnostics only."""
    version = re.search(r'Vndk version (\d+) is not supported\.\s*'
                        r'Supported versions in framework manifest are:\s*\[([\d\s]*)\]', text)
    libraries = re.search(r'Vndk libs incompatible for version (\d+)\.', text)
    sdk = re.search(r'The following System SDK versions are required by device\s+'
                    r'compatibility matrix but not supported by the framework manifest:\s*'
                    r'\[([\d,\s]*)\]\.\s*Supported versions are:\s*\[([\d,\s]*)\]', text)
    return {'unsupported_vndk_version': version.group(1) if version else None,
            'framework_supported_vndk_versions': re.findall(r'\d+', version.group(2)) if version else None,
            'vndk_library_list_mismatch_version': libraries.group(1) if libraries else None,
            'missing_system_sdk_versions': re.findall(r'\d+', sdk.group(1)) if sdk else None,
            'framework_supported_system_sdk_versions': re.findall(r'\d+', sdk.group(2)) if sdk else None}


def hypothetical_version(xml: bytes, old: str, new: str) -> bytes:
    """Patch one temporary snapshot field; no image or archive is ever touched."""
    if not xml or len(xml) > inventory.MAX_XML_BYTES or b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
        raise PolicyProbeError('Unsafe or oversized VINTF XML')
    root = ET.fromstring(xml)
    if root.tag != 'manifest' or root.get('type') != 'device':
        raise PolicyProbeError('Unexpected device VINTF manifest')
    versions = root.findall('./sepolicy/version')
    if len(versions) != 1 or (versions[0].text or '').strip() != old or new != VERSION:
        raise PolicyProbeError('VINTF hypothetical input field differs from audited 30.0')
    versions[0].text = new
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def hypothetical_framework_vndk(xml: bytes) -> bytes:
    """Add only a VNDK-30 declaration in a disposable framework snapshot."""
    vndk.parse_vndk_xml(xml, 'manifest', 'framework')
    root = ET.fromstring(xml)
    existing = [(version.text or '').strip() for version in root.findall('./vendor-ndk/version')]
    if existing != ['34']:
        raise PolicyProbeError('Framework VNDK versions differ from the audited input')
    section = ET.SubElement(root, 'vendor-ndk')
    ET.SubElement(section, 'version').text = '30'
    candidate = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    parsed = vndk.parse_vndk_xml(candidate, 'manifest', 'framework')
    if [row['version'] for row in parsed['vendor_ndk']] != ['34', '30']:
        raise PolicyProbeError('Unexpected counterfactual VNDK declaration')
    return candidate


def test_vintf_hypothesis(sandbox: Path) -> dict:
    path = sandbox / 'snapshot' / MANIFEST
    if path.is_symlink() or not path.is_file():
        raise PolicyProbeError('Pinned temporary vendor manifest missing')
    original = path.read_bytes()
    base, base_text = check.run_isolated(sandbox, '/snapshot', None)
    base['additional_diagnostics'] = vintf_extended_diagnostics(base_text)
    replacement = hypothetical_version(original, '30.0', VERSION)
    path.chmod(0o644)
    try:
        path.write_bytes(replacement)
        path.chmod(0o444)
        alternative, alternative_text = check.run_isolated(sandbox, '/snapshot', None)
        alternative['additional_diagnostics'] = vintf_extended_diagnostics(alternative_text)
    finally:
        path.chmod(0o644)
        path.write_bytes(original)
        path.chmod(0o444)
    if path.read_bytes() != original:
        raise PolicyProbeError('Temporary VINTF snapshot restoration failed')
    framework_path = sandbox / 'snapshot/system_ext/etc/vintf/manifest.xml'
    if framework_path.is_symlink() or not framework_path.is_file():
        raise PolicyProbeError('Pinned temporary framework manifest missing')
    original_framework = framework_path.read_bytes()
    replacement_framework = hypothetical_framework_vndk(original_framework)
    try:
        path.chmod(0o644)
        path.write_bytes(replacement)
        path.chmod(0o444)
        framework_path.chmod(0o644)
        framework_path.write_bytes(replacement_framework)
        framework_path.chmod(0o444)
        combined, combined_text = check.run_isolated(sandbox, '/snapshot', None)
        combined['additional_diagnostics'] = vintf_extended_diagnostics(combined_text)
    finally:
        path.chmod(0o644)
        path.write_bytes(original)
        path.chmod(0o444)
        framework_path.chmod(0o644)
        framework_path.write_bytes(original_framework)
        framework_path.chmod(0o444)
    if path.read_bytes() != original or framework_path.read_bytes() != original_framework:
        raise PolicyProbeError('Combined temporary VINTF snapshot restoration failed')
    return {'original': base,
            'hypothetical': alternative,
            'hypothetical_change': 'temporary VINTF sepolicy field 30.0 to vendor mapping-file version 31.0 only',
            'combined_hypothetical': combined,
            'combined_change': 'temporary sepolicy 31.0 plus framework declaration of VNDK 30',
            'temporary_snapshot_restored': True,
            'not_a_package_change': True,
            'warning': 'Counterfactual tests only: neither policy compilation nor snapshot results prove either declaration is valid or boots.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--otatools', type=Path, required=True)
    parser.add_argument('--avbtool', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if not args.work.is_dir() or args.work.is_symlink() or any(args.work.iterdir()):
        raise PolicyProbeError('Work directory must be new, empty and not a symlink')
    if args.report.exists() or args.report.is_symlink() or not args.report.parent.is_dir():
        raise PolicyProbeError('Report must be a new path')
    sandbox = args.work / 'sandbox'
    sandbox.mkdir()
    tool = prepare_secilc(args.otatools, sandbox)
    avb_tool = avb_verify.prepare(sandbox, args.avbtool)
    print('Running APEX AVB positive, corruption, invalid-signature and unsigned synthetic controls', flush=True)
    avb_controls = avb_verify.run_controls(sandbox, args.work, args.avbtool)
    print('Running compiler positive, unresolved-symbol and neverallow synthetic controls', flush=True)
    synthetic = controls(sandbox)
    reference_synthetic = reference_controls(sandbox)
    check_controls = check.run_controls(sandbox)
    print('All compiler and VINTF synthetic controls passed before candidate access', flush=True)
    snapshot = sandbox / 'snapshot'
    for part in check.MAPPINGS:
        (snapshot / part).mkdir(parents=True, exist_ok=True)
    seen, policy_rows, mapping_version, vndk_rows = {}, [], {}, []
    apex_result, apex_providers = {}, set()
    collector = vendor_abi.Collector()
    symbol_collector = vndk_symbols.Collector()
    def capture_vendor(entry, size, parsed):
        collector.capture_vendor_file(entry, size, parsed)
        symbol_collector.capture_consumer(entry, size, parsed)
    def capture(part, path, data):
        check.capture_snapshot(snapshot, seen, part, path, data)
    def capture_extra(image, part):
        capture_partition(image, part, sandbox / 'policy', policy_rows, mapping_version)
        vndk_rows.append(vndk.scan_partition(image, part))
        if part == 'system_ext':
            observed, providers = vndk_apex.inspect_system_ext(
                image, avb_verifier=lambda payload: avb_verify.verify_isolated(sandbox, payload),
                provider_observer=symbol_collector.capture_provider)
            apex_result.update(observed)
            apex_providers.update(providers)
        elif part == 'vendor':
            vendor_elf.scan_vendor(image, capture=capture_vendor)
    downloads = args.work / 'downloads'
    downloads.mkdir()
    candidate = draft.download_existing_draft(downloads)
    before = emu.regular_identity(candidate, draft.CANDIDATE_BYTES, draft.CANDIDATE_SHA256)
    with (ROOT / 'synthetica-project/original-baseline.lock.json').open(encoding='utf-8') as f:
        specs = inventory.part_specs(json.load(f))
    docs, groups = [], []
    for parts in (('system', 'system_ext', 'vendor'), ('product',)):
        more, _roots, group = inventory.audit_group(candidate, downloads, parts, specs,
                                                     capture=capture, scan_extra=capture_extra)
        docs.extend(more)
        groups.append(group)
    check.verify_inventory(docs, seen)
    vndk_declarations = vndk.snapshot_declarations(snapshot, seen)
    print('Compiling actual bounded policy snapshot with neverallow checks enabled', flush=True)
    strict_args = candidate_args(policy_rows)
    compile_result = compile_isolated(sandbox, strict_args, 'candidate')
    print('Comparing against reference AOSP init flags on disposable output only', flush=True)
    # This isolated comparison reproduces init's compile-time assertion flag;
    # it does not alter SELinux runtime enforcement or relax the strict result.
    reference_args = [strict_args[0], '-N', *strict_args[1:]]
    reference_result = compile_isolated(sandbox, reference_args, 'reference_candidate')
    print('Testing a restored, temporary VINTF sepolicy-version hypothesis', flush=True)
    vintf = test_vintf_hypothesis(sandbox)
    for guest, item in seen.items():
        path = snapshot / guest.lstrip('/')
        if path.stat().st_size != item['bytes'] or check.sha256_file(path) != item['sha256']:
            raise PolicyProbeError('A VINTF snapshot file did not match its initial hash')
    for row in policy_rows:
        if row['status'] == 'read':
            path = sandbox / 'policy' / row['name']
            if path.stat().st_size != row['bytes'] or check.sha256_file(path) != row['sha256']:
                raise PolicyProbeError('A captured policy file changed during the test')
    after = emu.regular_identity(candidate, draft.CANDIDATE_BYTES, draft.CANDIDATE_SHA256)
    result = {
        'schema': 'synthetica-boot-first-policy-compatibility-probe-v1',
        'status': 'host_diagnostics_only_not_a_repair_or_flash_approval',
        'candidate_before': before, 'candidate_after': after,
        'same_super_as_candidate_03_sha256': '3ae6b934491d3828b43904070a17bab89d56ddf0a79d599b11fd9cb701476673',
        'tool': tool, 'compiler_controls': synthetic, 'checkvintf_controls': check_controls,
        'runtime_reference_controls': reference_synthetic,
        'verified_extents_and_super': groups, 'policy_inputs': policy_rows,
        'vndk_candidate_inventory': vndk_rows, 'vndk_declarations': vndk_declarations,
        'existing_vndk30_apex': apex_result,
        'apex_avb_verifier': avb_tool, 'apex_avb_synthetic_controls': avb_controls,
        'vendor_executable_references_to_vndk30': vndk_apex.summarize_vendor_references(
            collector, apex_providers, apex_result.get('payload', {}).get('filesystem') == 'ext4'),
        'selected_vndk30_symbol_version_observations': symbol_collector.summarize(),
        'verified_vendor_mapping_version': mapping_version,
        'compiler': compile_result, 'runtime_reference_compiler': reference_result,
        'vintf_hypothesis': vintf,
        'all_snapshot_inputs_unchanged_after_execution': True,
        'limitations': [
            'Host secilc is from a pinned AOSP build, not proven identical to the ROM compiler.',
            'Output policydb version 30 follows the cited AOSP init build, not an observed device kernel.',
            'Strict compilation keeps neverallow checks enabled; the separately labelled AOSP init comparison uses -N only on disposable host output.',
            'Reference -N skips compiler assertions; it does not disable SELinux device enforcement, and its output is never shipped or installed.',
            'Actual ODM, SKU, genfs selection, userdebug policy, APEX and device kernel state are unknown.',
            'APEX AVB verification uses its embedded key; it does not establish signer trust, outer APK signing, device AVB or activation.',
            'Versioned symbol observations cover only selected direct vendor executable references and do not resolve Android linker behavior or ABI.',
            'On-disk VNDK files, symlinks and declarations cannot prove activation, provenance, signer trust or ABI compatibility.',
            'VINTF version change is only a counterfactual temporary snapshot, not a validated or applied fix.',
            'Neither host compile nor VINTF snapshot proves AVB, recovery acceptance, policy load, HAL ABI or boot.',
            'No package, image, security setting, device or recovery was modified or tested.',
        ],
    }
    with args.report.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('Targeted host-only policy diagnostic finished; no device verdict.', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (PolicyProbeError, check.CheckAuditError, inventory.VintfAuditError, vndk.VndkAuditError,
            vndk_apex.VndkApexError, avb_verify.AvbProbeError, vndk_symbols.SymbolProbeError,
            vendor_abi.AbiAuditError, vendor_elf.ElfMetadataError,
            draft.DraftTestError, emu.SimulationError, OSError, ValueError,
            zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f'::error title=Policy compatibility probe stopped::{exc}', file=sys.stderr)
        raise SystemExit(1)
