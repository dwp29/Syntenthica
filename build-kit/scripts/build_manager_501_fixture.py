#!/usr/bin/env python3
"""Build a debug-only, isolated production-screen UI fixture. NOT a Manager.

Uses the actual 5.0.1 MainActivity/Home/Settings/Customization and theme files,
with root/JNI entry points replaced, startup fetch/install disabled, no privileged
payload, no network permission, a different package and simulated status text.
Never install the real Manager or this fixture on a user's phone.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_501_themes as app

FIXTURE_ID = 'net.ember.labs.fixture501'
DISABLED = '{ throw IllegalStateException("UI fixture: privileged backend disabled") }'


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise RuntimeError(f'Expected exactly one fixture patch in {path}: {old[:100]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def kotlin_mask(text: str) -> str:
    """Mask strings/comments while keeping offsets and code braces for source editing."""
    out = list(text)
    i = 0
    while i < len(text):
        marker = None
        if text.startswith('//', i): marker = 'line'
        elif text.startswith('/*', i): marker = 'comment'
        elif text.startswith('"""', i): marker = 'triple'
        elif text[i] == '"': marker = 'string'
        elif text[i] == "'": marker = 'char'
        if marker is None:
            i += 1
            continue
        start = i
        if marker == 'line':
            end = text.find('\n', i + 2)
            i = len(text) if end < 0 else end
        elif marker == 'comment':
            depth = 1
            i += 2
            while i < len(text) and depth:
                if text.startswith('/*', i): depth += 1; i += 2
                elif text.startswith('*/', i): depth -= 1; i += 2
                else: i += 1
            if depth: raise ValueError('Unclosed Kotlin comment')
        elif marker == 'triple':
            end = text.find('"""', i + 3)
            if end < 0: raise ValueError('Unclosed Kotlin triple string')
            i = end + 3
        else:
            quote = text[i]
            i += 1
            while i < len(text):
                if text[i] == '\\': i += 2
                elif text[i] == quote: i += 1; break
                else: i += 1
            else: raise ValueError('Unclosed Kotlin string/character')
        for index in range(start, min(i, len(text))):
            if text[index] != '\n': out[index] = ' '
    return ''.join(out)


def balanced_end(mask: str, start: int, opening: str, closing: str) -> int:
    if mask[start] != opening:
        raise ValueError('Expected opening delimiter')
    depth = 0
    for index in range(start, len(mask)):
        if mask[index] == opening: depth += 1
        elif mask[index] == closing:
            depth -= 1
            if depth == 0: return index + 1
    raise ValueError('Unbalanced Kotlin source')


def disable_ksu_cli(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    mask = kotlin_mask(text)
    changes = []
    found = set()
    # Top-level only. Every callable in this backend file is either disabled or
    # explicitly retained as a UI-only activity refresh; no shell method remains.
    for match in re.finditer(r'(?m)^(?:(?:private|suspend|inline)\s+)*fun\s+', mask):
        start = match.start()
        paren = mask.find('(', match.end())
        name_match = re.search(r'([A-Za-z_]\w*)\s*$', mask[match.end():paren])
        if not name_match: raise ValueError('Cannot identify KsuCli function')
        name = name_match.group(1)
        found.add(name)
        end_params = balanced_end(mask, paren, '(', ')')
        i, parens, angles = end_params, 0, 0
        while i < len(mask):
            ch = mask[i]
            if ch == '(': parens += 1
            elif ch == ')': parens -= 1
            elif ch == '<': angles += 1
            elif ch == '>': angles = max(0, angles - 1)
            elif ch in '{=' and parens == 0 and angles == 0: break
            i += 1
        if i == len(mask): raise ValueError(f'No body for {name}')
        header = text[start:i].rstrip()
        if mask[i] == '{':
            end = balanced_end(mask, i, '{', '}')
        else:
            line_end = mask.find('\n', i)
            if line_end < 0: line_end = len(mask)
            open_brace = mask.find('{', i, line_end)
            end = balanced_end(mask, open_brace, '{', '}') if open_brace >= 0 else line_end
        if name in ('refreshActivity', 'restartActivity'):
            continue  # UI-only; no process, shell, network or privileged operation
        # The fixture deliberately renders a *simulated* full-featured Manager
        # to exercise the real rooted-layout branches, without obtaining root.
        canned = {
            'rootAvailable': ': Boolean = true',
            'getFeatureStatus': '= "unsupported"',
            'getFeaturePersistValue': '= null',
            'getSuSFS': '= ""', 'getMetaModule': '= ""',
            'getModuleCount': '= 0', 'getSuperuserCount': '= 0',
            'execKsud': '= false', 'reboot': '{ }',
        }
        replacement = header + ' ' + canned.get(name, DISABLED)
        changes.append((start, end, replacement))
    required = {'rootAvailable', 'createRootShell', 'createRootShellBuilder', 'execKsud', 'install',
                'listModules', 'getFeatureStatus', 'reboot', 'flashAnyKernelZip', 'getSuSFS', 'getMetaModule'}
    if not required <= found:
        raise ValueError(f'Missing expected backend functions: {required - found}')
    for start, end, replacement in reversed(changes):
        text = text[:start] + replacement + text[end:]
    for prohibited in ('Shell.cmd(', 'ShellUtils.fastCmd', 'Shell.Builder.create(', 'setCommands(',
                       '"/system/bin/reboot', 'debug su'):
        if prohibited in text:
            raise ValueError(f'Fixture backend still contains executable shell entry: {prohibited}')
    path.write_text(text, encoding='utf-8')


def disable_natives(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    init = '    init {\n        System.loadLibrary("kernelsu")\n    }\n'
    if text.count(init) != 1: raise ValueError('Expected one native library initialization')
    text = text.replace(init, '    // UI fixture: JNI is absent.\n', 1)
    defaults = {'Int': '0', 'IntArray': 'intArrayOf()', 'Boolean': 'false'}
    properties = []
    def property_stub(m: re.Match[str]) -> str:
        name, typ = m.group(1), m.group(2)
        if typ not in defaults: raise ValueError(f'Unexpected native property type: {typ}')
        properties.append(name)
        value = {'managerUAPIVersion': '4', 'kernelUAPIVersion': '4',
                 'version': '33188', 'isManager': 'true'}.get(name, defaults[typ])
        return f'    val {name}: {typ}\n        get() = {value}'
    text = re.sub(r'(?m)^    val (\w+): (\w+)\n\s+external get\s*$', property_stub, text)
    if set(properties) != {'version', 'allowList', 'isSafeMode', 'isLkmMode', 'isLkmBundled',
                           'isLateLoadMode', 'isManager', 'kernelUAPIVersion', 'managerUAPIVersion'}:
        raise ValueError(f'Unexpected native property set: {properties}')
    def method_stub(m: re.Match[str]) -> str:
        signature = m.group(1)
        name = signature.split('(', 1)[0]
        return_type = signature.rsplit(': ', 1)[1]
        canned = {'Boolean': 'false', 'Int': '0', 'String?': 'null', 'Profile': 'Profile(key ?: "", uid)'}
        if return_type not in canned: raise ValueError(f'Unexpected native method type: {return_type}')
        value = '"Simulated"' if name == 'getHookMode' else canned[return_type]
        return '    fun ' + signature + ' = ' + value
    text, count = re.subn(r'(?m)^    external fun (\w+\([^\n]*\): [^\n]+)$', method_stub, text)
    if count < 15 or 'external ' in text: raise ValueError('Failed to replace every JNI call')
    old = ('    fun isFullFeatured(): Boolean {\n'
           '        return isManager && kernelUAPIVersion == managerUAPIVersion && com.rifsxd.ksunext.ui.util.rootAvailable()\n'
           '    }')
    if text.count(old) != 1: raise ValueError('Full-featured guard changed')
    text = text.replace(old, '    fun isFullFeatured(): Boolean = true // simulated UI data only', 1)
    path.write_text(text, encoding='utf-8')


def prepare(src: Path, *, baseline50: bool = False) -> None:
    if baseline50:
        app.base50.prepare_tree(src)
    else:
        app.prepare_tree(src)
    main = src / 'manager/app/src/main'
    java = main / 'java/com/rifsxd/ksunext'
    gradle = src / 'manager/app/build.gradle.kts'
    replace_once(gradle, 'applicationId = "net.ember.labs"', f'applicationId = "{FIXTURE_ID}"')
    replace_once(gradle, 'dependencies {\n    implementation(libs.androidx.activity.compose)',
                 'dependencies {\n    testImplementation("junit:junit:4.13.2")\n    implementation(libs.androidx.activity.compose)')
    tests = src / 'manager/app/src/test/java/com/rifsxd/ksunext/ui/theme'
    tests.mkdir(parents=True, exist_ok=True)
    for test in (app.ASSETS / 'tests').glob('*.kt'):
        if not baseline50 or test.name == 'ThemeLogic50Test.kt':
            shutil.copy2(test, tests / test.name)
    replace_once(gradle, '''    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
        }
    }
''', '')
    text = gradle.read_text(encoding='utf-8')
    start = text.index('tasks.register<Copy>("mergeScripts")')
    end = text.index('\ndependencies {', start)
    gradle.write_text(text[:start] + '// UI fixture: no recovery/installer scripts\n' + text[end:], encoding='utf-8')
    for directory in ('jniLibs', 'cpp', 'resources'):
        shutil.rmtree(main / directory, ignore_errors=True)
    for script in (main / 'assets').glob('*.sh'):
        script.unlink()
    # Remove any INTERNET permission that a library manifest might merge in.
    (main / 'AndroidManifest.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" xmlns:tools="http://schemas.android.com/tools">
    <uses-permission android:name="android.permission.INTERNET" tools:node="remove" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" tools:node="remove" />
    <application android:name=".KernelSUApplication" android:allowBackup="false"
        android:label="SIMULATED UI TEST — NOT MANAGER" android:theme="@style/Theme.KernelSU">
        <activity android:name=".ui.MainActivity" android:exported="true" android:theme="@style/Theme.KernelSU">
            <intent-filter><action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" /></intent-filter>
        </activity>
    </application>
</manifest>
''', encoding='utf-8')
    disable_natives(java / 'Natives.kt')
    disable_ksu_cli(java / 'ui/util/KsuCli.kt')
    (java / 'ui/util/SELinuxChecker.kt').write_text('''package com.rifsxd.ksunext.ui.util
import androidx.compose.runtime.Composable
@Composable fun getSELinuxStatus(): String = "Simulated"
''', encoding='utf-8')
    replace_once(java / 'KernelSUApplication.kt', '        Shell.setDefaultBuilder(createRootShellBuilder(true))\n', '')
    activity = java / 'ui/MainActivity.kt'
    replace_once(activity, '''        lifecycleScope.launch {
            if (superUserViewModel.appList.isEmpty()) {
                superUserViewModel.fetchAppList()
            }
            if (moduleViewModel.moduleList.isEmpty()) {
                moduleViewModel.fetchModuleList()
            }
        }
''', '        // UI fixture: no privileged or network startup fetches.\n')
    replace_once(activity, '        if (Natives.isManager) install()\n', '        // UI fixture: installation disabled.\n')
    replace_once(java / 'ui/screen/Home.kt',
                 'subtitle = "${BuildConfig.VERSION_NAME}  •  UAPI v$managerUAPIVersion",',
                 'subtitle = "SIMULATED UI  •  NO ROOT",')
    # Integrity checks: the production UI files and dock are used, not a hand-made demo.
    dock_marker = 'val dockShape = MaterialTheme.shapes.extraLarge' if baseline50 else 'managerDockSpec(LocalManagerStyle.current)'
    for path, marker in ((java / 'ui/MainActivity.kt', dock_marker),
                         (java / 'ui/screen/Home.kt', 'IosHeroCard('),
                         (java / 'ui/screen/Settings.kt', 'fun SettingScreen('),
                         (java / 'ui/screen/Customization.kt', 'NeonAppearanceControls(')):
        if marker not in path.read_text(encoding='utf-8'):
            raise ValueError(f'Actual production UI marker missing: {path} / {marker}')
    print('[fixture501] Real Manager screen compositions; isolated simulated backend, no network or native payload', flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True, help='pinned upstream checkout, not a phone')
    p.add_argument('--baseline50', action='store_true', help='build a safe 5.0 fixture for a simulated upgrade test')
    p.add_argument('--verify-only', action='store_true')
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix='synthetica501-ui-fixture-') as tmp:
        source = Path(tmp) / 'source'
        shutil.copytree(args.source, source)
        prepare(source, baseline50=args.baseline50)
        if args.verify_only:
            print('[done] Fixture prepared; no APK built')
            return
        manager = source / 'manager'
        subprocess.run([str(manager / 'gradlew'), ':app:testDebugUnitTest', ':app:assembleDebug', '--no-daemon', '--stacktrace'],
                       cwd=manager, check=True)
        apks = list((manager / 'app/build/outputs/apk/debug').glob('*.apk'))
        if len(apks) != 1: raise RuntimeError('Expected exactly one debug UI fixture APK')
        output = Path(os.environ['THEMES501_FIXTURE_OUTPUT'])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists(): raise RuntimeError('Refusing to overwrite fixture output')
        shutil.copy2(apks[0], output)
        print('SIMULATED UI FIXTURE ONLY:', output, hashlib.sha256(output.read_bytes()).hexdigest(), flush=True)


if __name__ == '__main__':
    main()
