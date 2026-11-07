#!/usr/bin/env python3
"""Exercise the separate 3.1 preview on an Android emulator, NEVER a phone.

This test installs only the debug-signed preview, after checking the transport and
Android emulator properties. It does not install or exercise the root Manager.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

PACKAGE = 'net.ember.labs.neon31preview'
ACTIVITY = f'{PACKAGE}/com.rifsxd.ksunext.PreviewActivity'


class Emulator:
    def __init__(self, serial: str, output: Path):
        if not re.fullmatch(r'emulator-\d+', serial):
            raise ValueError('Refusing to run: serial is not an emulator transport')
        self.serial = serial
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        if self.adb('shell', 'getprop', 'ro.kernel.qemu').strip() != '1':
            raise ValueError('Refusing to run: Android does not identify itself as an emulator')
        avd = self.adb('emu', 'avd', 'name')
        if not avd.strip() or 'KO' in avd:
            raise ValueError('Refusing to run: emulator console did not confirm an AVD')
        print(f'Emulator verified: {serial} / {avd.strip()}', flush=True)

    def adb(self, *args: str, binary: bool = False) -> str | bytes:
        proc = subprocess.run(['adb', '-s', self.serial, *args], check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        return proc.stdout if binary else proc.stdout.decode('utf-8', errors='replace')

    def install_and_start(self, apk: Path) -> None:
        self.adb('install', '-r', str(apk))
        self.adb('shell', 'am', 'start', '-W', '-n', ACTIVITY)
        time.sleep(4)

    def dump(self, name: str) -> ET.Element:
        self.adb('shell', 'uiautomator', 'dump', '/sdcard/neon31-window.xml')
        data = self.adb('exec-out', 'cat', '/sdcard/neon31-window.xml', binary=True)
        assert isinstance(data, bytes)
        (self.output / f'{name}.xml').write_bytes(data)
        return ET.fromstring(data)

    @staticmethod
    def bounds(node: ET.Element) -> tuple[int, int, int, int]:
        match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
        if not match:
            raise ValueError(f'Invalid UI node bounds: {node.get("bounds")}')
        return tuple(int(value) for value in match.groups())  # type: ignore[return-value]

    def find(self, root: ET.Element, label: str) -> list[ET.Element]:
        result = []
        for node in root.iter('node'):
            if node.get('text') == label or node.get('content-desc') == label:
                x1, y1, x2, y2 = self.bounds(node)
                if x2 > x1 and y2 > y1:
                    result.append(node)
        return result

    def tap(self, label: str, dump_name: str, scroll: bool = False) -> None:
        for attempt in range(12 if scroll else 1):
            if scroll and attempt == 6:
                # The previous action may have left the page at the bottom.
                for _ in range(5):
                    self.adb('shell', 'input', 'swipe', '540', '650', '540', '1600', '250')
            root = self.dump(f'{dump_name}-{attempt}')
            nodes = self.find(root, label)
            if nodes:
                # Text descendants are enough: taps bubble to their selectable row.
                node = min(nodes, key=lambda n: (self.bounds(n)[2] - self.bounds(n)[0]) *
                           (self.bounds(n)[3] - self.bounds(n)[1]))
                x1, y1, x2, y2 = self.bounds(node)
                self.adb('shell', 'input', 'tap', str((x1 + x2) // 2), str((y1 + y2) // 2))
                time.sleep(1.5)
                return
            if scroll:
                self.adb('shell', 'input', 'swipe', '540', '1590', '540', '700', '450')
                time.sleep(0.7)
        raise AssertionError(f'UI label not found: {label!r}')

    def wait_for(self, label: str, dump_name: str, *, scroll: bool = False) -> ET.Element:
        for attempt in range(10):
            root = self.dump(f'{dump_name}-{attempt}')
            if self.find(root, label):
                return root
            if scroll:
                self.adb('shell', 'input', 'swipe', '540', '1550', '540', '700', '400')
            time.sleep(0.8)
        raise AssertionError(f'UI label did not appear: {label!r}')

    @staticmethod
    def all_text(root: ET.Element) -> str:
        return '\n'.join(node.get('text', '') for node in root.iter('node'))

    def assert_staging_empty(self) -> None:
        files = self.adb('shell', 'run-as', PACKAGE, 'find', 'cache/neon31-preflight', '-type', 'f')
        if files.strip():
            raise AssertionError(f'Preview preflight staging files were not cleaned: {files}')

    def screenshot(self, name: str) -> Path:
        data = self.adb('exec-out', 'screencap', '-p', binary=True)
        assert isinstance(data, bytes) and data.startswith(b'\x89PNG\r\n\x1a\n')
        path = self.output / f'{name}.png'
        path.write_bytes(data)
        return path

    def prefs(self) -> str:
        return self.adb('shell', 'run-as', PACKAGE, 'cat', 'shared_prefs/settings.xml')  # type: ignore[return-value]

    def assert_checked(self, root: ET.Element, label: str, expected: bool) -> None:
        parents = {child: parent for parent in root.iter() for child in parent}
        for node in self.find(root, label):
            current = node
            while current is not None:
                if current.get('checkable') == 'true' and current.get('checked') == str(expected).lower():
                    return
                current = parents.get(current)
        raise AssertionError(f'{label!r} not marked checked={expected}')

    def choose_radio(self, label: str, name: str) -> ET.Element:
        # Compose transitions can leave a previous tab briefly on screen. Retry
        # a radio tap (idempotent) until its accessibility state settles.
        for attempt in range(3):
            self.tap(label, f'{name}-tap-{attempt}')
            root = self.dump(name)
            try:
                self.assert_checked(root, label, True)
                return root
            except AssertionError:
                time.sleep(1)
        raise AssertionError(f'{label!r} did not become selected after retries')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{64}', args.sha256):
        raise ValueError('Expected a lowercase SHA-256')
    if hashlib.sha256(args.apk.read_bytes()).hexdigest() != args.sha256:
        raise ValueError('Preview APK checksum mismatch')
    emulator = Emulator(args.serial, args.output)
    emulator.adb('shell', 'settings', 'put', 'global', 'animator_duration_scale', '1')
    emulator.install_and_start(args.apk)
    home = emulator.dump('home')
    assert emulator.find(home, 'Device Check'), 'Device Check entry missing'
    emulator.tap('Settings', 'open-settings')
    emulator.choose_radio('Light', 'settings-light')
    light_png = emulator.screenshot('settings-light')
    if '<string name="neon_theme">light</string>' not in emulator.prefs():
        raise AssertionError('Light mode was not persisted')
    emulator.choose_radio('Dark', 'settings-dark')
    dark_png = emulator.screenshot('settings-dark')
    try:
        from PIL import Image, ImageStat
        with Image.open(BytesIO(light_png.read_bytes())) as image:
            light_luma = ImageStat.Stat(image.convert('L')).mean[0]
        with Image.open(BytesIO(dark_png.read_bytes())) as image:
            dark_luma = ImageStat.Stat(image.convert('L')).mean[0]
        print(f'Mean screenshot brightness: light={light_luma:.1f}, dark={dark_luma:.1f}', flush=True)
        if light_luma < dark_luma + 40:
            raise AssertionError('Light and dark modes did not render distinctly')
    except ImportError as exc:
        raise RuntimeError('Pillow is required for the light/dark visual assertion') from exc
    # AMOLED keeps the actual canvas black, rather than painting a full-screen
    # gradient on top of black. Sample the outer margin, excluding system bars.
    emulator.choose_radio('AMOLED black', 'settings-amoled')
    amoled_png = emulator.screenshot('settings-amoled')
    if '<string name="neon_theme">amoled</string>' not in emulator.prefs():
        raise AssertionError('AMOLED mode was not persisted')
    with Image.open(BytesIO(amoled_png.read_bytes())) as image:
        pixels = image.convert('RGB')
        w, h = pixels.size
        samples = [pixels.getpixel((x, y)) for x in (1, w - 2)
                   for y in range(h // 8, 7 * h // 8)]
        black_ratio = sum(pixel == (0, 0, 0) for pixel in samples) / len(samples)
    print(f'AMOLED black canvas edge ratio: {black_ratio:.3f}', flush=True)
    if black_ratio < 0.80:
        raise AssertionError('AMOLED canvas was not actually black')

    # Follow-system mode should respond to Android's day/night configuration.
    emulator.adb('shell', 'cmd', 'uimode', 'night', 'no')
    time.sleep(3)
    emulator.choose_radio('Follow system', 'settings-system')
    system_light = emulator.screenshot('settings-system-light')
    if '<string name="neon_theme">system</string>' not in emulator.prefs():
        raise AssertionError('Follow-system mode was not persisted')
    emulator.adb('shell', 'cmd', 'uimode', 'night', 'yes')
    time.sleep(4)
    system_dark = emulator.screenshot('settings-system-dark')
    with Image.open(BytesIO(system_light.read_bytes())) as image:
        sys_light_luma = ImageStat.Stat(image.convert('L')).mean[0]
    with Image.open(BytesIO(system_dark.read_bytes())) as image:
        sys_dark_luma = ImageStat.Stat(image.convert('L')).mean[0]
    print(f'Follow-system brightness: light={sys_light_luma:.1f}, dark={sys_dark_luma:.1f}', flush=True)
    if sys_light_luma < sys_dark_luma + 40:
        raise AssertionError('Follow-system mode did not respond to day/night')
    emulator.adb('shell', 'cmd', 'uimode', 'night', 'no')
    time.sleep(3)
    emulator.choose_radio('Light', 'settings-restored-light')
    emulator.tap('Normal', 'choose-glow', scroll=True)
    emulator.tap('Neon motion', 'disable-motion', scroll=True)
    prefs = emulator.prefs()
    for needle in ('<string name="neon_theme">light</string>', '<string name="neon_glow">normal</string>',
                   '<boolean name="neon_motion" value="false"'):
        if needle not in prefs:
            raise AssertionError(f'Missing persisted preference: {needle}')
    (args.output / 'preferences-before.xml').write_text(prefs)
    emulator.adb('shell', 'am', 'force-stop', PACKAGE)
    emulator.adb('shell', 'am', 'start', '-W', '-n', ACTIVITY)
    time.sleep(4)
    restarted = emulator.prefs()
    if prefs != restarted:
        raise AssertionError('Appearance preferences changed after restarting the preview')
    (args.output / 'preferences-after.xml').write_text(restarted)
    emulator.tap('Device Check', 'open-device-check', scroll=True)
    time.sleep(4)
    root = emulator.dump('device-check')
    emulator.screenshot('device-check')
    for label in ('Device Check', 'LIVE OVERVIEW', 'Copy selected device info'):
        if not emulator.find(root, label):
            raise AssertionError(f'Device Check label missing: {label}')

    # The dialog starts with nothing selected and Copy disabled; choosing one
    # section must not put other sections in the generated preview.
    emulator.tap('Copy selected device info', 'copy-dialog-open')
    root = emulator.wait_for('Copy', 'copy-empty')
    copy_nodes = emulator.find(root, 'Copy')
    if not copy_nodes or any(node.get('enabled') != 'false' for node in copy_nodes):
        raise AssertionError('Copy was enabled before any section was selected')
    emulator.assert_checked(root, 'Device identifiers (model and codename)', False)
    emulator.tap('Device identifiers (model and codename)', 'copy-select-device')
    root = emulator.dump('copy-selected')
    emulator.assert_checked(root, 'Device identifiers (model and codename)', True)
    if 'Codename:' not in emulator.all_text(root):
        emulator.adb('shell', 'input', 'swipe', '540', '1440', '540', '850', '400')
        root = emulator.dump('copy-preview')
    text = emulator.all_text(root)
    if 'Codename:' not in text or 'Kernel:' in text:
        raise AssertionError('Selected-only device summary preview was missing or included system data')
    emulator.screenshot('copy-dialog')
    emulator.tap('Copy', 'copy-confirm')
    time.sleep(1)
    if emulator.find(emulator.dump('copy-complete'), 'Copy'):
        raise AssertionError('Copy dialog did not close')
    emulator.wait_for('GPU current frequency', 'device-performance', scroll=True)
    emulator.wait_for('zram0 configured size', 'device-zram', scroll=True)
    emulator.adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
    time.sleep(2)

    # This separate preview reuses the actual preflight and Manager dialog but
    # has stub FlashIt values and no root or installer backend.
    emulator.tap('ZIP preflight preview', 'open-zip-preview', scroll=True)
    emulator.wait_for('Test module ZIP', 'zip-preview')
    emulator.tap('Test module ZIP', 'zip-module')
    root = emulator.wait_for('Module ZIP check (1/1)', 'zip-module-dialog')
    module_text = emulator.all_text(root)
    if 'Detected type: Module' not in module_text or not re.search(r'\b[0-9a-f]{64}\b', module_text):
        raise AssertionError('Module confirmation omitted the detected type or SHA-256')
    emulator.screenshot('zip-dialog')
    emulator.tap('Cancel', 'zip-module-cancel')
    emulator.wait_for('Blocked or canceled; no installation occurred.', 'zip-canceled', scroll=True)
    emulator.assert_staging_empty()

    emulator.tap('Test unknown ZIP', 'zip-unknown', scroll=True)
    root = emulator.wait_for('ZIP cannot be installed', 'zip-unknown-dialog')
    if 'No recognizable module or AnyKernel3 marker' not in emulator.all_text(root):
        raise AssertionError('Unknown ZIP was not explicitly blocked')
    emulator.tap('OK', 'zip-unknown-close')
    emulator.wait_for('Blocked or canceled; no installation occurred.', 'zip-unknown-result', scroll=True)
    emulator.assert_staging_empty()

    emulator.tap('Test unexpected kernel', 'zip-mismatch', scroll=True)
    root = emulator.wait_for('ZIP cannot be installed', 'zip-mismatch-dialog')
    if 'This source is for modules' not in emulator.all_text(root):
        raise AssertionError('Unexpected kernel from a module source was not blocked')
    emulator.tap('OK', 'zip-mismatch-close')
    emulator.wait_for('Blocked or canceled; no installation occurred.', 'zip-mismatch-result', scroll=True)
    emulator.assert_staging_empty()

    emulator.tap('Test changed ZIP', 'zip-tamper', scroll=True)
    emulator.wait_for('Module ZIP check (1/1)', 'zip-tamper-dialog')
    emulator.tap('Continue to installation', 'zip-tamper-approve')
    emulator.wait_for('Tamper blocked; no installation occurred.', 'zip-tamper-result', scroll=True)
    emulator.assert_staging_empty()

    emulator.tap('Test two modules', 'zip-batch-cancel', scroll=True)
    emulator.wait_for('Module ZIP check (1/2)', 'zip-batch-first')
    emulator.tap('Continue to installation', 'zip-batch-first-approve')
    emulator.wait_for('Module ZIP check (2/2)', 'zip-batch-second')
    emulator.tap('Cancel', 'zip-batch-second-cancel')
    emulator.wait_for('Blocked or canceled; no installation occurred.', 'zip-batch-canceled', scroll=True)
    emulator.assert_staging_empty()

    emulator.tap('Test two modules', 'zip-batch-confirm', scroll=True)
    emulator.wait_for('Module ZIP check (1/2)', 'zip-batch-first-again')
    emulator.tap('Continue to installation', 'zip-batch-approve-first')
    emulator.wait_for('Module ZIP check (2/2)', 'zip-batch-second-again')
    emulator.tap('Continue to installation', 'zip-batch-approve-second')
    emulator.wait_for('Verified approved copy; no installation occurred.', 'zip-batch-success', scroll=True)
    emulator.assert_staging_empty()

    emulator.tap('Test kernel ZIP', 'zip-kernel', scroll=True)
    root = emulator.wait_for('Kernel ZIP check (1/1)', 'zip-kernel-dialog')
    kernel_text = emulator.all_text(root)
    if 'AnyKernel3 kernel installer' not in kernel_text or not re.search(r'\b[0-9a-f]{64}\b', kernel_text):
        raise AssertionError('Kernel confirmation omitted the detected type or SHA-256')
    emulator.tap('Continue to installation', 'zip-kernel-approve')
    emulator.wait_for('Verified approved copy; no installation occurred.', 'zip-kernel-success', scroll=True)
    emulator.assert_staging_empty()

    emulator.adb('shell', 'dumpsys', 'gfxinfo', PACKAGE)
    print('PASS: preview themes, saved settings, selective copy, read-only diagnostics, ZIP confirmations and hash guard.', flush=True)
    print('All ZIP flows were simulations. The real Manager, root, flashing and physical devices were not tested.', flush=True)


if __name__ == '__main__':
    main()
