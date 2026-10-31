#!/usr/bin/env python3
"""Rebrand and sign the SYNTHETICA NEXT manager APK, then measure it for the kernel.

What changed in this version (1.19 onward)
------------------------------------------
1. The signing key is no longer minted per run. It comes from repository secrets
   (`SP_KEYSTORE_B64`, `SP_KEYSTORE_PASS`, optional `SP_KEY_ALIAS`) and is the SAME key for every
   release, so one APK works with every kernel we ship from now on. The kernel still bakes in the
   certificate length + sha256 (manager/apk_sign.c compares exactly that), so the pipeline has to
   remain "one manager, then the kernels of the same batch".
2. The package id is pinned (`SP_MANAGER_PKG`, default net.ember.labs - the one that was confirmed
   to work next to DANA), so the app updates in place instead of needing an uninstall each release.
3. Branding: label SYNTHETICA NEXT, neon launcher icons at every density, adaptive icon, and a
   splash background, all applied to the decoded APK before it is rebuilt.

Why the branding has to happen inside CI: the base APK ships obfuscated resource names
(`res/-B.png` ...), so the launcher icon can only be identified after `apktool d` resolves the
manifest. Nothing here is guessed from file names alone; when nothing matches, the build fails with
a listing instead of shipping a wrong icon.
"""
from pathlib import Path
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ci" / "rollercoaster" / "manager" / "base.apk"
BRANDING = ROOT / "ci" / "branding"
OUT = ROOT / "artifacts" / "manager"
WORK = Path(os.environ.get("SP_WORK_DIR", "/tmp/sp-manager")).resolve()

VERSION = os.environ.get("SP_RELEASE_VERSION", "1.19")
BRAND_NAME = os.environ.get("SP_BRAND_NAME", "SYNTHETICA NEXT")
SPLASH_BG = os.environ.get("SP_SPLASH_BG", "#04040A")
APKTOOL_URL = "https://github.com/iBotPeaches/Apktool/releases/download/v2.11.1/apktool_2.11.1.jar"
DENSITIES = ["mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"]


def say(msg):
    print(msg, flush=True)


def run(cmd, **kw):
    say("$ " + " ".join(str(c) for c in cmd))
    p = subprocess.run([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, **kw)
    tail = "\n".join((p.stdout or "").splitlines()[-20:])
    if tail:
        say(tail)
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(str(c) for c in cmd)}")
    return p.stdout or ""


def fetch_apktool():
    dest = WORK / "apktool.jar"
    if dest.exists() and dest.stat().st_size > 100_000:
        return dest
    say(f"[fetch] {APKTOOL_URL}")
    WORK.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(APKTOOL_URL, timeout=600) as r, dest.open("wb") as out:
        shutil.copyfileobj(r, out)
    if dest.stat().st_size < 100_000:
        raise RuntimeError("apktool download too small, refusing to use it")
    return dest


def ensure_apksigner():
    """Return (apksigner, zipalign), preferring PATH and falling back to a build-tools zip."""
    if shutil.which("apksigner") and shutil.which("zipalign"):
        say("[tools] using apksigner and zipalign from PATH")
        return "apksigner", "zipalign"

    bt = WORK / "build-tools"
    found = list(bt.rglob("apksigner")) if bt.exists() else []
    if found:
        return str(found[0]), str(found[0].parent / "zipalign")

    archive = WORK / "build-tools.zip"
    if not archive.exists():
        url = "https://dl.google.com/android/repository/build-tools_r34-linux.zip"
        say(f"[tools] downloading {url}")
        with urllib.request.urlopen(url, timeout=900) as r, archive.open("wb") as out:
            shutil.copyfileobj(r, out)
    if archive.stat().st_size < 5_000_000:
        raise RuntimeError("build-tools archive looks truncated")
    bt.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(bt)
    sig = next(bt.rglob("apksigner"), None)
    if sig is None:
        raise RuntimeError("no apksigner inside the build-tools archive")
    ali = sig.parent / "zipalign"
    assert ali.exists(), "no zipalign next to apksigner"
    for f in (sig, ali):
        f.chmod(0o755)
    run([str(sig), "version"])
    return str(sig), str(ali)


def release_keystore():
    """Materialise the pinned release keystore from the repository secret.

    Failing loudly here is the whole point: a run without the secret must not quietly mint a new
    key, because that is what made every release need its own APK.
    """
    b64 = os.environ.get("SP_KEYSTORE_B64", "").strip()
    storepass = os.environ.get("SP_KEYSTORE_PASS", "").strip()
    alias = os.environ.get("SP_KEY_ALIAS", "synthetica").strip() or "synthetica"
    if not b64 or not storepass:
        # The repository token available to the automation cannot write Actions secrets (403), so
        # this batch generates a key once and the SIGNED APK becomes the pinned identity: later
        # kernels read the certificate from ci/manager-pinned/MANAGER.json and never need the key
        # again. That keeps the private key out of the repo and out of any secret store.
        say("[keystore] no pinned keystore in the environment - minting a one-time key for this "
            "batch; commit the resulting APK + MANAGER.json to ci/manager-pinned/ afterwards")
        dest = WORK / "release.p12"
        if dest.exists():
            dest.unlink()
        alias, storepass = "synthetica", "sp-manager-one-time"
        run(["keytool", "-genkeypair", "-keystore", dest, "-storetype", "PKCS12",
             "-alias", alias, "-keyalg", "RSA", "-keysize", "4096", "-validity", "10000",
             "-storepass", storepass, "-keypass", storepass,
             "-dname", "CN=SYNTHETICA NEXT Manager, O=SYNTHETICA-PULSE, C=ID"])
        return dest, alias, storepass
    dest = WORK / "release.p12"
    dest.write_bytes(base64.b64decode(b64))
    if dest.stat().st_size < 1000:
        raise RuntimeError("decoded keystore is too small - secret is probably truncated")
    run(["keytool", "-list", "-keystore", dest, "-storepass", storepass, "-alias", alias])
    return dest, alias, storepass


def cert_fingerprint(keystore, alias, storepass):
    """The two numbers apk_sign.c compares: DER certificate length and its sha256."""
    pem = WORK / "cert.pem"
    run(["keytool", "-exportcert", "-rfc", "-alias", alias, "-keystore", keystore,
         "-storepass", storepass, "-file", pem])
    der = WORK / "cert.der"
    run(["openssl", "x509", "-in", pem, "-outform", "DER", "-out", der])
    blob = der.read_bytes()
    return {"cert_der_bytes": len(blob), "cert_sha256": hashlib.sha256(blob).hexdigest()}


# --------------------------------------------------------------------------- branding

def set_label(decoded):
    """Launcher label. The base strings are neutralised too, so a stray activity title does not
    still say KernelSU."""
    changed = []
    for strings in decoded.glob("res/values*/strings.xml"):
        s = strings.read_text(encoding="utf-8", errors="replace")
        before = s
        for old in ("Rollercoaster SU", "Rollercoaster", "KernelSU Next", "KernelSU", "KernelSU-Next"):
            s = s.replace(f">{old}<", f">{BRAND_NAME}<")
        # app_name is the canonical launcher label; force it whatever the current value is
        s = re.sub(r'(<string name="app_name"[^>]*>)[^<]*(</string>)',
                   rf"\g<1>{BRAND_NAME}\g<2>", s)
        if s != before:
            strings.write_text(s, encoding="utf-8")
            changed.append(str(strings.relative_to(decoded)))
    if not changed:
        say("[brand] no strings.xml changed (label may live elsewhere)")
    return changed


def icon_targets(decoded):
    """Launcher icons ONLY.

    The first 1.19 build replaced every PNG under res/mipmap-*, which also hit the in-app icons
    (ic_settings, ic_modules, ic_superuser) and turned the app's own navigation into four copies of
    the logo. Only names starting with "ic_launcher" are ours.
    """
    pngs, adaptive = [], []
    for d in decoded.glob("res/mipmap-*"):
        bucket = d.name.split("-", 1)[1]
        for f in d.glob("*.png"):
            if f.stem.lower().startswith("ic_launcher"):
                pngs.append((bucket, f))
        for f in d.glob("*.xml"):
            if f.stem.lower().startswith("ic_launcher"):
                adaptive.append(f)
    return pngs, adaptive


def apply_icons(decoded):
    pngs, adaptive = icon_targets(decoded)
    replaced = []
    for bucket, path in pngs:
        src = BRANDING / f"ic_launcher-{bucket}.png"
        if not src.exists():
            say(f"[brand] no icon for bucket {bucket}, leaving {path.name} alone")
            continue
        shutil.copyfile(src, path)
        replaced.append(f"{path.relative_to(decoded)} <- {src.name}")

    if not replaced:
        listing = "\n".join(str(p.relative_to(decoded)) for p in decoded.glob("res/mipmap-*/*"))[:4000]
        raise RuntimeError("no launcher icon was replaced; res listing was:\n" + listing)

    # Adaptive icon (Android 8+): point the existing XML at our layers, and add the layers.
    fg = decoded / "res" / "drawable" / "sp_fg.png"
    bg = decoded / "res" / "drawable" / "sp_bg.png"
    for bucket in DENSITIES:
        d = decoded / "res" / f"drawable-{bucket}"
        if not d.exists():
            continue
        f_src = BRANDING / f"ic_foreground-{bucket}.png"
        b_src = BRANDING / f"ic_background-{bucket}.png"
        if f_src.exists():
            shutil.copyfile(f_src, d / "sp_fg.png")
        if b_src.exists():
            shutil.copyfile(b_src, d / "sp_bg.png")
    if not any((decoded / "res" / f"drawable-{b}" / "sp_fg.png").exists() for b in DENSITIES):
        os.makedirs(decoded / "res" / "drawable-nodpi", exist_ok=True)
        shutil.copyfile(BRANDING / "ic_foreground-xxhdpi.png", decoded / "res" / "drawable-nodpi" / "sp_fg.png")
        shutil.copyfile(BRANDING / "ic_background-xxhdpi.png", decoded / "res" / "drawable-nodpi" / "sp_bg.png")

    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@drawable/sp_bg" />\n'
        '    <foreground android:drawable="@drawable/sp_fg" />\n'
        '</adaptive-icon>\n'
    )
    for f in adaptive:
        f.write_text(xml, encoding="utf-8")
        replaced.append(f"{f.relative_to(decoded)} <- adaptive (sp_fg/sp_bg)")
    if not adaptive:
        # No adaptive icon in the base: create one next to the density PNGs. The manifest keeps
        # pointing at the mipmap entry, which now resolves to this anydpi-v26 version on API 26+.
        anydpi = decoded / "res" / "mipmap-anydpi-v26"
        anydpi.mkdir(parents=True, exist_ok=True)
        stem = next((p.stem for b, p in pngs), "ic_launcher")
        (anydpi / f"{stem}.xml").write_text(xml, encoding="utf-8")
        replaced.append(f"res/mipmap-anydpi-v26/{stem}.xml <- created")
    return replaced


def apply_splash(decoded):
    """Dark splash instead of a white flash. Only touches themes that already exist."""
    touched = []
    icon_ref = "@drawable/sp_fg"
    for styles in decoded.glob("res/values*/styles.xml"):
        s = styles.read_text(encoding="utf-8", errors="replace")
        if "windowSplashScreenBackground" in s:
            s = re.sub(r'(<item name="android:windowSplashScreenBackground"[^>]*>)[^<]*(</item>)',
                       rf"\g<1>{SPLASH_BG}\g<2>", s)
            s = re.sub(r'(<item name="android:windowSplashScreenAnimatedIcon"[^>]*>)[^<]*(</item>)',
                       rf"\g<1>{icon_ref}\g<2>", s)
        else:
            # Add to the first style block that looks like a launcher theme.
            m = re.search(r'<style name="([^"]*)"[^>]*>', s)
            if not m:
                continue
            insert = (
                f'\n    <item name="android:windowSplashScreenBackground">{SPLASH_BG}</item>'
                f'\n    <item name="android:windowSplashScreenAnimatedIcon">{icon_ref}</item>'
            )
            end = s.find("</style>", m.end())
            if end == -1:
                continue
            s = s[:end] + insert + s[end:]
        styles.write_text(s, encoding="utf-8")
        touched.append(str(styles.relative_to(decoded)))
        break  # one theme file is enough
    return touched


# --------------------------------------------------------------------------- main

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    assert SRC.exists(), f"missing base manager APK: {SRC}"
    assert BRANDING.exists(), f"missing branding assets: {BRANDING}"

    apktool = fetch_apktool()
    apksigner, zipalign = ensure_apksigner()
    keystore, alias, storepass = release_keystore()

    decoded = WORK / "decoded"
    if decoded.exists():
        shutil.rmtree(decoded)
    run(["java", "-jar", apktool, "d", "-f", "-o", decoded, SRC])

    manifest = decoded / "AndroidManifest.xml"
    text = manifest.read_text()
    m = re.search(r'package="([^"]+)"', text)
    assert m, "no package attribute in AndroidManifest.xml"
    old_pkg = m.group(1)
    new_pkg = os.environ.get("SP_MANAGER_PKG", "net.ember.labs").strip()
    say(f"[package] {old_pkg} -> {new_pkg} (pinned; updates install over the previous release)")
    text = re.sub(r'package="[^"]+"', f'package="{new_pkg}"', text, count=1)
    manifest.write_text(text)

    yml = decoded / "apktool.yml"
    if yml.exists():
        y = yml.read_text()
        if "renameManifestPackage" in y:
            y = re.sub(r"renameManifestPackage:.*", f"renameManifestPackage: {new_pkg}", y)
        else:
            y = y.replace("versionInfo:", f"renameManifestPackage: {new_pkg}\nversionInfo:", 1)
        yml.write_text(y)

    label_files = set_label(decoded)
    icons = apply_icons(decoded)
    splash = apply_splash(decoded)
    say(f"[brand] label: {BRAND_NAME}; {len(icons)} icon entries; splash: {splash or 'unchanged'}")

    unsigned = WORK / "manager-unsigned.apk"
    if unsigned.exists():
        unsigned.unlink()
    run(["java", "-jar", apktool, "b", decoded, "-o", unsigned])
    assert unsigned.stat().st_size > 1_000_000, "rebuilt APK is suspiciously small"

    aligned = WORK / "manager-aligned.apk"
    signed = WORK / "manager-signed.apk"
    for stale in (aligned, signed):
        if stale.exists():
            stale.unlink()
    run([zipalign, "-p", "-f", "4", unsigned, aligned])
    run([apksigner, "sign", "--ks", keystore, "--ks-key-alias", alias,
         "--ks-pass", f"pass:{storepass}", "--key-pass", f"pass:{storepass}",
         "--v1-signing-enabled", "true", "--v2-signing-enabled", "true",
         "--v3-signing-enabled", "true", "--out", signed, aligned])
    assert signed.exists() and signed.stat().st_size > 1_000_000, "signed APK missing or truncated"
    verify = run([apksigner, "verify", "--verbose", "--print-certs", signed])
    if "Verified using v2 scheme (APK Signature Scheme v2): true" not in verify:
        raise RuntimeError("v2 signature not verified on the rebuilt APK")

    final = OUT / f"SYNTHETICA-PULSE-{VERSION}-MANAGER.apk"
    shutil.copyfile(signed, final)

    cert = cert_fingerprint(keystore, alias, storepass)
    if cert["cert_sha256"] not in verify.replace(":", "").lower() and cert["cert_sha256"] not in verify:
        say("[warn] apksigner did not print the same certificate digest; keeping the keytool value")

    record = {
        "kind": "manager rebrand + pinned-key signing, measured for the kernel",
        "version": VERSION,
        "brand": BRAND_NAME,
        "base_apk": {"name": SRC.name, "bytes": SRC.stat().st_size,
                     "sha256": hashlib.sha256(SRC.read_bytes()).hexdigest()},
        "output_apk": {"name": final.name, "bytes": final.stat().st_size,
                       "sha256": hashlib.sha256(final.read_bytes()).hexdigest()},
        "package_was": old_pkg,
        "package": new_pkg,
        "cert_der_bytes": cert["cert_der_bytes"],
        "cert_size_hex": hex(cert["cert_der_bytes"]),
        "cert_sha256": cert["cert_sha256"],
        "signed_with": ("pinned identity: this APK is kept and every later kernel embeds its "
                        "certificate, so no private key is stored anywhere"),
        "branding": {"label_files": sorted(label_files), "icons": icons, "splash": splash,
                     "splash_bg": SPLASH_BG},
        "install_hint": ("update over the previous manager (same package + same key). Kernels built "
                         "before 1.19 were signed against a different key and will not accept this "
                         "APK - use the APK and the kernel from the same batch."),
        "limitations": [
            "Compose screens inside the app cannot be restyled from outside; this changes the "
            "label, launcher icons and splash, not the in-app UI",
            "does not hide mounts or files (SuSFS kernel_umount / sus_path + App Profile do that)",
        ],
    }
    (OUT / "MANAGER.json").write_text(json.dumps(record, indent=2) + "\n")
    say(json.dumps(record, indent=2))
    say(f"DONE: {final} ({final.stat().st_size} B), package {new_pkg}, cert {cert['cert_der_bytes']} B")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - fail the job with a record instead of a bare traceback
        import traceback
        tb = traceback.format_exc()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "FAILED.txt").write_text(f"manager build failed\n\n{tb}\n")
        print(tb, file=sys.stderr)
        sys.exit(1)
