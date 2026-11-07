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
        for attempt in range(6 if scroll else 1):
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
            self.adb('shell', 'input', 'swipe', '540', '1590', '540', '700', '450')
            time.sleep(0.7)
        raise AssertionError(f'UI label not found: {label!r}')

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
    for label in ('Device Check', 'LIVE OVERVIEW', 'RAM in use / total'):
        if not emulator.find(root, label):
            raise AssertionError(f'Device Check label missing: {label}')
    emulator.adb('shell', 'dumpsys', 'gfxinfo', PACKAGE)
    print('PASS: preview light, dark, AMOLED and system rendering, saved settings and Device Check on emulator.', flush=True)
    print('The real Manager, root and physical devices were not tested.', flush=True)


if __name__ == '__main__':
    main()
