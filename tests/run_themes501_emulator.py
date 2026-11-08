#!/usr/bin/env python3
"""Test actual Manager compositions in isolated, simulated AVD fixtures only.

The two APKs have a separate fixture package, no network permission, no JNI or
root backend and no installer payload. Status values are fabricated UI data,
NOT a root test. Refuses non-emulator transports and never installs the Manager.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys
import time
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_neon31_emulator as base
import verify_themes501_fixture_apk as verify

base.PACKAGE = 'net.ember.labs.fixture501'
base.ACTIVITY = base.PACKAGE + '/com.rifsxd.ksunext.ui.MainActivity'


class FixtureEmulator(base.Emulator):
    def screen_size(self) -> tuple[int, int]:
        text = self.adb('shell', 'wm', 'size')
        values = re.findall(r'(?:Physical|Override) size:\s*(\d+)x(\d+)', text)
        if not values:
            raise ValueError(f'Cannot determine AVD screen size: {text}')
        return tuple(map(int, values[-1]))  # type: ignore[return-value]

    def swipe(self, *, down_page: bool) -> None:
        w, h = self.screen_size()
        y1, y2 = (int(h * .80), int(h * .32)) if down_page else (int(h * .32), int(h * .80))
        self.adb('shell', 'input', 'swipe', str(w // 2), str(y1), str(w // 2), str(y2), '350')
        time.sleep(.4)

    def tap(self, label: str, dump_name: str, scroll: bool = False) -> None:
        for attempt in range(20 if scroll else 3):
            if scroll and attempt == 10:
                for _ in range(6):
                    self.swipe(down_page=False)
            root = self.dump(f'{dump_name}-{attempt}')
            nodes = self.find(root, label)
            if nodes:
                node = min(nodes, key=lambda n: (self.bounds(n)[2] - self.bounds(n)[0]) *
                           (self.bounds(n)[3] - self.bounds(n)[1]))
                x1, y1, x2, y2 = self.bounds(node)
                self.adb('shell', 'input', 'tap', str((x1 + x2) // 2), str((y1 + y2) // 2))
                time.sleep(1.3)
                return
            if scroll:
                self.swipe(down_page=True)
            else:
                time.sleep(.8)
        raise AssertionError(f'Production UI label not found: {label!r}')

    def wait_for(self, label: str, dump_name: str, *, scroll: bool = False) -> ET.Element:
        for attempt in range(16):
            root = self.dump(f'{dump_name}-{attempt}')
            if self.find(root, label):
                return root
            if scroll:
                self.swipe(down_page=True)
            else:
                time.sleep(.7)
        raise AssertionError(f'Production UI label did not appear: {label!r}')


def choose(e: FixtureEmulator, label: str, name: str) -> None:
    for attempt in range(3):
        e.tap(label, f'{name}-tap-{attempt}', scroll=True)
        root = e.dump(f'{name}-chosen-{attempt}')
        try:
            e.assert_checked(root, label, True)
            return
        except AssertionError:
            time.sleep(.7)
    raise AssertionError(f'{label!r} did not become selected')


def back(e: FixtureEmulator) -> None:
    e.adb('shell', 'input', 'keyevent', '4')
    time.sleep(1.5)


def to_customize(e: FixtureEmulator, name: str) -> None:
    # Restore the actual bottom bar if a prior status check hid it while scrolling.
    for _ in range(5):
        e.swipe(down_page=False)
    e.tap('Settings', f'{name}-open-settings')
    e.tap('Customization', f'{name}-open-customization', scroll=True)
    e.wait_for('Pixel Signal', f'{name}-design-page', scroll=True)


def to_home(e: FixtureEmulator, name: str, *, settings_screenshot: bool = False) -> ET.Element:
    back(e)  # Customization -> actual Settings
    if settings_screenshot:
        e.screenshot('settings-' + name)
    back(e)  # Settings -> actual Home via production BackHandler
    e.wait_for('Synthetica Manager', f'home-{name}')
    # The dock must reappear when returning from a screen that was scrolled.
    return e.wait_for('Home', f'home-dock-{name}')


def brightness(path: Path) -> float:
    with Image.open(path) as image:
        return ImageStat.Stat(image.convert('L')).mean[0]


def difference(a: Path, b: Path) -> float:
    with Image.open(a) as x, Image.open(b) as y:
        w, h = x.size
        box = (0, h // 10, w, h * 9 // 10)
        delta = ImageChops.difference(x.convert('RGB').crop(box), y.convert('RGB').crop(box))
        return sum(ImageStat.Stat(delta).mean) / 3


def assert_amoled_black(path: Path) -> None:
    with Image.open(path) as image:
        pix = image.convert('RGB')
        w, h = pix.size
        samples = [pix.getpixel((x, y)) for x in (1, w - 2) for y in range(h // 8, 7 * h // 8)]
        ratio = sum(p == (0, 0, 0) for p in samples) / len(samples)
    print(f'AMOLED black edge ratio: {ratio:.3f}', flush=True)
    if ratio < .80:
        raise AssertionError('AMOLED canvas not black')


def one_bounds(e: FixtureEmulator, root: ET.Element, label: str) -> tuple[int, int, int, int]:
    nodes = e.find(root, label)
    if not nodes:
        raise AssertionError(f'Actual Home missing {label!r}')
    return e.bounds(nodes[0])


def check_home(e: FixtureEmulator, root: ET.Element, name: str) -> dict[str, tuple[int, int, int, int]]:
    text = e.all_text(root)
    if 'SIMULATED UI' not in text:
        raise AssertionError('Fixture must visibly identify itself as simulated')
    for item in ('Synthetica Manager', 'Rooted', 'BUILT-IN'):
        if not e.find(root, item):
            raise AssertionError(f'Actual Home missing {item!r}: {name}')
    bounds = {label: one_bounds(e, root, label) for label in ('Synthetica Manager', 'Rooted', 'BUILT-IN')}
    a, b = bounds['Rooted'], bounds['BUILT-IN']
    overlap_x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    overlap_y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    if overlap_x * overlap_y:
        raise AssertionError(f'Status labels overlap on {name}: {a}, {b}')
    print(f'Actual Home bounds {name}: {bounds}', flush=True)
    return bounds


def check_dark_toolbar_icons(e: FixtureEmulator, root: ET.Element, image: Path, name: str) -> None:
    # In the original dark screenshot these interactive icons were black on black.
    # Verify their *pixels*, not just the presence of accessibility labels.
    with Image.open(image) as screenshot:
        gray = screenshot.convert('L')
        for label in ('Install', 'Reboot'):
            box = one_bounds(e, root, label)
            crop = gray.crop(box)
            hist = crop.histogram()
            visible = sum(hist[150:]) / max(1, crop.width * crop.height)
            print(f'Toolbar {name}/{label} bright pixel ratio: {visible:.3f}', flush=True)
            if visible < .01:
                raise AssertionError(f'{name} toolbar {label} lacks contrast on the dark background')


def require_hash(path: Path, expected: str) -> None:
    if not re.fullmatch('[0-9a-f]{64}', expected) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f'Fixture digest mismatch: {path}')
    verify.verify(path)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial', required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--baseline-sha256', required=True)
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    require_hash(args.baseline, args.baseline_sha256)
    require_hash(args.apk, args.sha256)
    e = FixtureEmulator(args.serial, args.output)
    e.adb('shell', 'settings', 'put', 'global', 'animator_duration_scale', '1')
    e.install_and_start(args.baseline)
    check_home(e, e.dump('baseline-home'), 'baseline-simulated')
    package_info = e.adb('shell', 'dumpsys', 'package', base.PACKAGE)
    if 'versionCode=60000' not in package_info:
        raise AssertionError('Baseline fixture version is not 5.0')

    # A real Android package update between safe fixtures with identical debug
    # signatures. It is NOT an update of the production signed Manager.
    to_customize(e, 'baseline')
    choose(e, 'Neon', 'baseline-neon')
    choose(e, 'Dark', 'baseline-dark')
    choose(e, 'Alternative B', 'baseline-accent')
    e.tap('Appearance motion', 'baseline-motion-off', scroll=True)
    saved = e.prefs()
    for needle in ('<string name="manager_visual_style">neon</string>',
                   '<string name="neon_theme">dark</string>',
                   '<string name="neon_accent">violet</string>',
                   '<boolean name="neon_motion" value="false"'):
        if needle not in saved:
            raise AssertionError(f'Baseline preference missing: {needle}')
    (args.output / 'preferences-before-update.xml').write_text(saved)
    e.adb('install', '-r', str(args.apk))
    e.adb('shell', 'am', 'start', '-W', '-n', base.ACTIVITY)
    time.sleep(4)
    package_info = e.adb('shell', 'dumpsys', 'package', base.PACKAGE)
    if 'versionCode=60001' not in package_info:
        raise AssertionError('Fixture update did not advance version code')
    after = e.prefs()
    if saved != after:
        raise AssertionError('Appearance or other settings changed during fixture update')
    (args.output / 'preferences-after-update.xml').write_text(after)
    check_home(e, e.dump('home-after-update'), 'after-update-simulated')
    to_customize(e, 'verify-update')
    root = e.wait_for('Neon', 'verify-neon-after-update', scroll=True)
    e.assert_checked(root, 'Neon', True)

    styles = [('Pixel Signal', 'pixel'), ('Cyberpunk', 'cyberpunk'), ('iOS Glass', 'ios_glass'), ('Neon', 'neon')]
    screenshots: dict[str, Path] = {}
    geometry: dict[str, dict[str, tuple[int, int, int, int]]] = {}
    for index, (label, style_id) in enumerate(styles):
        if index:
            to_customize(e, 'open-' + style_id)
        choose(e, label, 'style-' + style_id)
        if f'<string name="manager_visual_style">{style_id}</string>' not in e.prefs():
            raise AssertionError(f'{style_id} selection was not saved')
        choose(e, 'Dark', 'dark-' + style_id)
        dark = e.screenshot('mode-dark-' + style_id)
        choose(e, 'Light', 'light-' + style_id)
        light = e.screenshot('mode-light-' + style_id)
        print(f'{label} light={brightness(light):.1f} dark={brightness(dark):.1f}', flush=True)
        if brightness(light) < brightness(dark) + 30:
            raise AssertionError(f'{label} light/dark not visibly different')
        choose(e, 'AMOLED black', 'amoled-' + style_id)
        assert_amoled_black(e.screenshot('mode-amoled-' + style_id))
        choose(e, 'Dark', 'visual-dark-' + style_id)
        home = to_home(e, style_id, settings_screenshot=True)
        geometry[style_id] = check_home(e, home, style_id)
        screenshots[style_id] = e.screenshot('home-' + style_id)
        check_dark_toolbar_icons(e, home, screenshots[style_id], style_id)
        e.tap('System & environment details', 'expand-details-' + style_id, scroll=True)
        e.wait_for('SELinux', 'expanded-selinux-' + style_id, scroll=True)
        # The production disclosure uses rememberSaveable across theme changes.
        # Close it again so the next style starts from the same known state.
        e.swipe(down_page=False)
        e.swipe(down_page=False)
        e.tap('System & environment details', 'collapse-details-' + style_id, scroll=True)

    for style_id in ('cyberpunk', 'ios_glass', 'neon'):
        delta = difference(screenshots['pixel'], screenshots[style_id])
        print(f'Actual Home visual difference pixel/{style_id}: {delta:.2f}', flush=True)
        if delta < 3.0:
            raise AssertionError(f'{style_id} did not visibly change actual Home')
        title = geometry[style_id]['Synthetica Manager']
        pixel = geometry['pixel']['Synthetica Manager']
        status = geometry[style_id]['Rooted']
        pixel_status = geometry['pixel']['Rooted']
        structural_delta = sum(abs(a-b) for a, b in zip(title, pixel)) + sum(abs(a-b) for a, b in zip(status, pixel_status))
        print(f'Actual Home semantic layout difference pixel/{style_id}: {structural_delta}px', flush=True)
        if structural_delta < 60:
            raise AssertionError(f'{style_id} did not materially rearrange actual Home content')

    prefs = e.prefs()
    e.adb('shell', 'am', 'force-stop', base.PACKAGE)
    e.adb('shell', 'am', 'start', '-W', '-n', base.ACTIVITY)
    time.sleep(4)
    if e.prefs() != prefs:
        raise AssertionError('Preferences changed after process restart')
    check_home(e, e.dump('restart-home'), 'restart')
    first = e.screenshot('motion-off-1')
    time.sleep(1.5)
    second = e.screenshot('motion-off-2')
    motion_delta = difference(first, second)
    print(f'Motion-off difference: {motion_delta:.5f}', flush=True)
    if motion_delta > .08:
        raise AssertionError('Motion-off screen did not settle')

    try:
        e.adb('shell', 'wm', 'size', '720x1280')
        e.adb('shell', 'settings', 'put', 'system', 'font_scale', '1.5')
        e.adb('shell', 'am', 'force-stop', base.PACKAGE)
        e.adb('shell', 'am', 'start', '-W', '-n', base.ACTIVITY)
        time.sleep(4)
        for label, style_id in styles:
            to_customize(e, 'small-open-' + style_id)
            choose(e, label, 'small-' + style_id)
            home = to_home(e, 'small-' + style_id)
            check_home(e, home, 'small-' + style_id)
            e.screenshot('home-small-' + style_id)
    finally:
        e.adb('shell', 'wm', 'size', 'reset')
        e.adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')

    packages = e.adb('shell', 'pm', 'list', 'packages')
    if f'package:{base.PACKAGE}' not in packages or 'package:net.ember.labs\n' in packages:
        raise AssertionError('Expected only the isolated fixture, never the real Manager')
    print('Production layouts, controls, modes, fixture update and small/large-font scenarios passed.', flush=True)
    print('All root status data was simulated. No live root, phone, boot or real Manager update was tested.', flush=True)


if __name__ == '__main__':
    main()
