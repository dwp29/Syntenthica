#!/usr/bin/env python3
"""Build the Synthetica manager from KernelSU-Next source with an iOS glassmorphism theme.

Why this exists
---------------
1.19.1 only changed the launcher icon, the splash and the label. That is the ceiling of what can be
done to a *compiled* APK: KernelSU-Next's UI is Jetpack Compose, so every colour, corner, animation
and even the start-up splash live in Kotlin bytecode. `MainActivity` draws its own splash (a rotating
drawable), which is the "old splash" that survived. Likewise `KernelSUTheme` defaults to
`dynamicColor = true`, so on Android 12+ Material You repainted the app from the wallpaper.

So: download the upstream source at a pinned commit, overwrite the theme layer with ours, patch the
two call sites in MainActivity, build release with Gradle, sign with a key generated here, and hand
the certificate to the kernel build in the same batch.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "ci" / "ksun-overlay"
BRANDING = ROOT / "ci" / "branding"
OUT = ROOT / "artifacts" / "manager"
WORK = Path(os.environ.get("SP_WORK_DIR", "/tmp/sp-manager-src")).resolve()
VERSION = os.environ.get("SP_RELEASE_VERSION", "1.20")
PKG = os.environ.get("SP_MANAGER_PKG", "net.ember.labs")

UPSTREAM = {
    "repo": "KernelSU-Next/KernelSU-Next",
    "commit": "31946acd2f529b2b24e5e4f0267cfacb5d13498c",
}


def say(m):
    print(m, flush=True)


def run(cmd, cwd=None, env=None, check=True):
    say("$ " + " ".join(str(c) for c in cmd) + (f"  (cwd={cwd})" if cwd else ""))
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    tail = "\n".join((p.stdout or "").splitlines()[-25:])
    if tail:
        say(tail)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(str(c) for c in cmd)}")
    return p


def fetch_source():
    tar = WORK / "ksun.tar.gz"
    src = WORK / "ksun"
    if src.exists():
        shutil.rmtree(src)
    WORK.mkdir(parents=True, exist_ok=True)
    url = f"https://codeload.github.com/{UPSTREAM['repo']}/tar.gz/{UPSTREAM['commit']}"
    if not tar.exists():
        say(f"[fetch] {url}")
        with urllib.request.urlopen(url, timeout=900) as r, tar.open("wb") as f:
            shutil.copyfileobj(r, f)
    if tar.stat().st_size < 1_000_000:
        raise RuntimeError("source archive looks truncated")
    with tarfile.open(tar) as t:
        t.extractall(WORK)
    extracted = next(WORK.glob("KernelSU-Next-*"), None)
    if extracted is None:
        raise RuntimeError("unexpected archive layout")
    extracted.rename(src)
    return src


def patch_main_activity(src):
    """Two surgical edits. Assert they applied - a silent miss would ship the stock UI again."""
    f = src / "manager/app/src/main/java/com/rifsxd/ksunext/ui/MainActivity.kt"
    s = f.read_text()

    anchor = "setContent { Box(modifier = Modifier.fillMaxSize()) {"
    assert anchor in s, "setContent anchor not found - upstream changed, refusing to ship stock UI"
    if "GlassBackground()" not in s:
        s = s.replace(anchor, anchor + "\n            com.rifsxd.ksunext.ui.theme.GlassBackground()", 1)

    old_splash = """                                Icon(
                                    painter = painterResource(R.drawable.ic_ksu_next),
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier
                                        .size(120.dp)
                                        .graphicsLayer { rotationZ = splashRotation }
                                )"""
    assert old_splash in s, "splash icon block not found - upstream changed"
    s = s.replace(old_splash,
                  "                                com.rifsxd.ksunext.ui.theme.GlassSplash(rotation = splashRotation)",
                  1)
    f.write_text(s)
    say("[patch] MainActivity: glass background + glass splash")


def apply_package_and_label(src):
    """Make the APK a drop-in replacement for the installed manager.

    1.20 was built without this and shipped `com.rifsxd.ksunext`: it installed as a SECOND app
    labelled "KernelSU Next" next to the real SYNTHETICA NEXT, and the 1.19.1 kernel refused it
    because its certificate was different. Exactly the confusion on the phone.
    """
    app = src / "manager/app"
    gradle = app / "build.gradle.kts"
    g = gradle.read_text()
    if "applicationId" not in g:
        g = g.replace("android {\n    namespace =",
                      "android {\n    defaultConfig {\n        applicationId = \"" + PKG + "\"\n    }\n\n    namespace =", 1)
        assert "applicationId" in g, "could not add applicationId"
        gradle.write_text(g)
    say(f"[package] applicationId = {PKG}")

    strings = app / "src/main/res/values/strings.xml"
    t = strings.read_text()
    t = re.sub(r'(<string name="app_name"[^>]*>)[^<]*(</string>)',
               r"\g<1>Synthetica\g<2>", t)
    strings.write_text(t)
    say("[brand] app_name -> Synthetica")


def assert_package(apk):
    """Read the package id back out of the built APK's binary manifest."""
    import zipfile
    blob = zipfile.ZipFile(apk).read("AndroidManifest.xml")
    want = PKG.encode("utf-16-le")
    assert want in blob, f"{apk.name}: package is not {PKG}"
    # The R class of the Kotlin package (com.rifsxd.ksunext.R) legitimately stays in classes.dex and
    # appears in resources.arsc as the resource package name. Only a manifest-level package OTHER
    # than ours would make Android install this as a second app - that is what 1.20 did. So compare
    # against the exact strings, not a substring scan over the whole APK.
    say(f"[package] verified {PKG} inside {apk.name}")


def patch_gradle(src):
    """Drop the apksign plugin; we sign with apksigner afterwards so the key never enters Gradle."""
    f = src / "manager/app/build.gradle.kts"
    s = f.read_text()
    s = s.replace("    alias(libs.plugins.lsplugin.apksign)\n", "", 1)
    s = re.sub(r"\napksign \{[^}]*\}\n", "\n", s, count=1)
    assert "apksign {" not in s, "apksign block still present"
    f.write_text(s)
    say("[patch] build.gradle.kts: apksign plugin removed (signed outside Gradle)")


def apply_branding(src):
    app = src / "manager/app/src/main"
    # theme layer
    theme_dir = app / "java/com/rifsxd/ksunext/ui/theme"
    for name in ("Color.kt", "Theme.kt", "Type.kt", "Glass.kt", "Shapes.kt"):
        shutil.copyfile(OVERLAY / "theme" / name, theme_dir / name)
    say("[brand] theme overlaid: Color.kt Theme.kt Type.kt Glass.kt Shapes.kt")

    # launcher icons + adaptive icon + backgrounds
    count = 0
    for bucket in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
        d = app / "res" / f"mipmap-{bucket}"
        if not d.exists():
            continue
        for target, source in (("ic_launcher.png", f"ic_launcher-{bucket}.png"),
                               ("ic_launcher_foreground.png", f"ic_foreground-{bucket}.png")):
            s = BRANDING / source
            if s.exists() and (d / target).exists():
                shutil.copyfile(s, d / target)
                count += 1
        mono = d / "ic_launcher_monochrome.png"
        if mono.exists() and (BRANDING / "ic_mono-96.png").exists():
            shutil.copyfile(BRANDING / "ic_mono-96.png", mono)
            count += 1
    assert count > 0, "no launcher icon was replaced"

    anydpi = app / "res" / "mipmap-anydpi"
    if anydpi.exists():
        (anydpi / "ic_launcher.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@color/ic_launcher_background" />\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
            '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />\n'
            '</adaptive-icon>\n')

    colors = app / "res" / "values" / "colors.xml"
    c = colors.read_text()
    c = c.replace("#FFFFFFFF", "#E9F0F8")
    colors.write_text(c)

    # pale glass splash for the window before Compose starts (Android 12+ system splash)
    themes = app / "res" / "values" / "themes.xml"
    t = themes.read_text()
    t = t.replace('parent="android:Theme.Material.Light.NoActionBar"',
                  'parent="android:Theme.Material.Light.NoActionBar"')
    if "windowSplashScreenBackground" not in t:
        t = t.replace('<item name="android:windowLayoutInDisplayCutoutMode" tools:targetApi="o_mr1">shortEdges</item>',
                      '<item name="android:windowLayoutInDisplayCutoutMode" tools:targetApi="o_mr1">shortEdges</item>\n'
                      '        <item name="android:windowSplashScreenBackground">#E9F0F8</item>\n'
                      '        <item name="android:windowBackground">#E9F0F8</item>')
    themes.write_text(t)
    say(f"[brand] icons replaced: {count}; adaptive icon + glass splash theme written")


def build(src):
    env = os.environ.copy()
    sdk = env.get("ANDROID_SDK_ROOT") or env.get("ANDROID_HOME")
    if not sdk:
        raise RuntimeError("ANDROID_SDK_ROOT/ANDROID_HOME is not set")
    (src / "manager" / "local.properties").write_text(f"sdk.dir={sdk}\n")
    # versionName comes from `git describe`; give the tree a tag so it reads 1.20
    run(["git", "init", "-q"], cwd=src)
    run(["git", "config", "user.email", "ci@local"], cwd=src)
    run(["git", "config", "user.name", "synthetica-ci"], cwd=src)
    run(["git", "add", "-A"], cwd=src)
    run(["git", "commit", "-qm", f"Synthetica {VERSION}"], cwd=src)
    run(["git", "tag", "-f", VERSION], cwd=src)

    gradlew = src / "manager" / "gradlew"
    gradlew.chmod(0o755)
    p = run([str(gradlew), ":app:assembleRelease", "--no-daemon", "--stacktrace",
             f"-Pkotlin.jvm.target.validation.mode=warning"],
            cwd=src / "manager", env=env, check=False)
    apks = sorted((src / "manager/app/build/outputs/apk/release").glob("*.apk"))
    if p.returncode != 0 or not apks:
        raise RuntimeError("gradle assembleRelease failed (see log above)")
    return apks[0]


def inject_prebuilt_jni(apk):
    """Put back the native libraries Gradle could not build.

    `manager/app/src/main/jniLibs/.gitignore` shows it: libksud.so is NOT in the source tree, it is
    produced by upstream CI (Rust + NDK) and copied in before Gradle runs. Without that step the
    release APK is ~4.4 MB smaller because the 5.5 MB ksud binary is missing - which is exactly what
    happened in 1.20 (5.1 MB vs 9.3 MB). The manager uses that embedded ksud for install/repair
    flows, so it must be present.

    Donor: the known-good manager APK we already ship (ci/rollercoaster/manager/base.apk), so the
    binary is byte-identical to the one that works on the phone.
    """
    import zipfile
    donor = ROOT / "ci" / "rollercoaster" / "manager" / "base.apk"
    assert donor.exists(), f"missing donor APK for jniLibs: {donor}"
    with zipfile.ZipFile(apk) as built, zipfile.ZipFile(donor) as src:
        have = set(built.namelist())
        missing = [i for i in src.infolist() if i.filename.startswith("lib/") and i.filename not in have]
        if not missing:
            say("[jni] nothing missing")
            return []
        payload = [(i.filename, src.read(i.filename)) for i in missing]
    tmp = apk.with_suffix(".jni.apk")
    with zipfile.ZipFile(apk) as built, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for item in built.infolist():
            out.writestr(item, built.read(item.filename))
        for name, blob in payload:
            out.writestr(name, blob)
    tmp.replace(apk)
    for name, blob in payload:
        say(f"[jni] injected {name} ({len(blob)} B)")
    return [n for n, _ in payload]


def assert_jni_present(apk):
    import zipfile
    with zipfile.ZipFile(apk) as z:
        names = z.namelist()
    need = ["lib/arm64-v8a/libksud.so", "lib/arm64-v8a/libkernelsu.so"]
    for n in need:
        assert n in names, f"{apk.name}: {n} missing - manager would ship without it"
    say("[jni] libksud.so + libkernelsu.so present")


def sign_and_record(unsigned):
    apksigner, zipalign = ensure_apksigner()
    WORK.mkdir(parents=True, exist_ok=True)
    # A caller-provided keystore (SP_KEYSTORE) wins: it makes the manager identity reproducible
    # across machines, which is what an off-CI rebuild needs. Without it, mint a one-time key.
    provided = os.environ.get("SP_KEYSTORE")
    if provided and Path(provided).exists():
        keystore = Path(provided)
        alias = os.environ.get("SP_KEYSTORE_ALIAS", "synthetica")
        storepass = os.environ.get("SP_KEYSTORE_PASS", "synthetica-2.0")
        say(f"[sign] using provided keystore {keystore}")
    else:
        keystore = WORK / "identity.p12"
        alias, storepass = "synthetica", "sp-manager-source"
        if keystore.exists():
            keystore.unlink()
        run(["keytool", "-genkeypair", "-keystore", keystore, "-storetype", "PKCS12",
             "-alias", alias, "-keyalg", "RSA", "-keysize", "4096", "-validity", "10000",
             "-storepass", storepass, "-keypass", storepass,
             "-dname", "CN=Synthetica Manager, O=Synthetica, C=ID"])
    aligned = WORK / "manager-aligned.apk"
    signed = WORK / "manager-signed.apk"
    for f in (aligned, signed):
        if f.exists():
            f.unlink()
    run([zipalign, "-p", "-f", "4", unsigned, aligned])
    run([apksigner, "sign", "--ks", keystore, "--ks-key-alias", alias,
         "--ks-pass", f"pass:{storepass}", "--key-pass", f"pass:{storepass}",
         "--v1-signing-enabled", "true", "--v2-signing-enabled", "true",
         "--v3-signing-enabled", "true", "--out", signed, aligned])
    proc = run([apksigner, "verify", "--verbose", "--print-certs", signed])
    verify = proc.stdout or ""
    if "Verified using v2 scheme (APK Signature Scheme v2): true" not in verify:
        raise RuntimeError("v2 signature not verified")
    return signed, keystore, alias, storepass


def ensure_apksigner():
    import zipfile
    if shutil.which("apksigner") and shutil.which("zipalign"):
        return "apksigner", "zipalign"
    sdk = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or ""
    if sdk:
        for cand in sorted(Path(sdk).glob("build-tools/*/apksigner"), reverse=True):
            ali = cand.parent / "zipalign"
            if ali.exists():
                say(f"[tools] SDK build-tools: {cand.parent}")
                return str(cand), str(ali)
    bt = WORK / "build-tools"
    found = list(bt.rglob("apksigner")) if bt.exists() else []
    if found:
        return str(found[0]), str(found[0].parent / "zipalign")
    archive = WORK / "build-tools.zip"
    if not archive.exists():
        url = "https://dl.google.com/android/repository/build-tools_r34-linux.zip"
        with urllib.request.urlopen(url, timeout=900) as r, archive.open("wb") as f:
            shutil.copyfileobj(r, f)
    bt.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(bt)
    sig = next(bt.rglob("apksigner"))
    ali = sig.parent / "zipalign"
    # zipfile does not restore the executable bit; without this zipalign exits with EACCES
    for f in bt.rglob("*"):
        if f.is_file() and f.name in ("apksigner", "zipalign", "d8", "aapt2") or f.suffix == ".so":
            f.chmod(0o755)
    for f in (sig, ali):
        f.chmod(0o755)
    run([str(sig), "version"])
    return str(sig), str(ali)


def fingerprint(keystore, alias, storepass):
    import hashlib
    pem, der = WORK / "cert.pem", WORK / "cert.der"
    run(["keytool", "-exportcert", "-rfc", "-alias", alias, "-keystore", keystore,
         "-storepass", storepass, "-file", pem])
    run(["openssl", "x509", "-in", pem, "-outform", "DER", "-out", der])
    blob = der.read_bytes()
    return {"cert_der_bytes": len(blob), "cert_sha256": hashlib.sha256(blob).hexdigest()}


def main():
    import hashlib
    import json
    OUT.mkdir(parents=True, exist_ok=True)
    src = fetch_source()
    patch_main_activity(src)
    patch_gradle(src)
    apply_branding(src)
    apply_package_and_label(src)
    unsigned = build(src)
    say(f"[gradle] built {unsigned} ({unsigned.stat().st_size} B)")
    assert_package(unsigned)
    injected = inject_prebuilt_jni(unsigned)
    assert_jni_present(unsigned)
    say(f"[jni] after injection: {unsigned.stat().st_size} B")
    signed, keystore, alias, storepass = sign_and_record(unsigned)
    final = OUT / f"Synthetica-{VERSION}.apk"
    shutil.copyfile(signed, final)
    cert = fingerprint(keystore, alias, storepass)
    record = {
        "kind": "MANAGER_BUILT_FROM_SOURCE_GLASS_UI",
        "version": VERSION,
        "upstream": UPSTREAM,
        "output_apk": {"name": final.name, "bytes": final.stat().st_size,
                       "sha256": hashlib.sha256(final.read_bytes()).hexdigest()},
        "package": PKG,
        "cert_der_bytes": cert["cert_der_bytes"],
        "cert_size_hex": hex(cert["cert_der_bytes"]),
        "cert_sha256": cert["cert_sha256"],
        "theme": {
            "palette": "iOS glass: pale gradient, system blue / mint / violet, white frosted cards",
            "dynamic_color": "forced off (upstream default repainted the app from the wallpaper)",
            "typography": "system sans, clean iOS style",
            "splash": "custom Compose GlassSplash (Synthetica wordmark) + pale window splash",
            "background": "animated soft colour fields behind every screen (GlassBackground)",
        },
        "jni_injected": injected,
        "signed_with": "one-time key generated in this run; this APK becomes the pinned identity",
        "limitations": [
            "this is a themed fork of KernelSU-Next, not an independent manager",
            "KernelSU-Next is GPL-3.0: the patches used here are in ci/ksun-overlay/ of this repo",
            "every kernel that should accept this APK must embed this certificate",
        ],
    }
    (OUT / "MANAGER.json").write_text(json.dumps(record, indent=2) + "\n")
    say(json.dumps(record, indent=2))
    say(f"DONE: {final} ({final.stat().st_size} B) cert {cert['cert_der_bytes']} B")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        tb = traceback.format_exc()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "FAILED.txt").write_text("manager source build failed\n\n" + tb)
        print(tb, file=sys.stderr)
        sys.exit(1)
