#!/usr/bin/env python3
"""Exercise the separate non-root 5.0 preview on a verified emulator only."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys
import time

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_neon31_emulator as base

base.PACKAGE = 'net.ember.labs.multitheme50preview'
base.ACTIVITY = f'{base.PACKAGE}/com.rifsxd.ksunext.PreviewActivity'


def choose(e: base.Emulator, label: str, name: str) -> None:
    for attempt in range(3):
        e.tap(label, f'{name}-tap-{attempt}', scroll=True)
        root = e.dump(f'{name}-{attempt}')
        try:
            e.assert_checked(root, label, True)
            return
        except AssertionError:
            time.sleep(1)
    raise AssertionError(f'{label!r} did not become selected')


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
        edge = [pix.getpixel((x, y)) for x in (1, w - 2) for y in range(h // 8, 7 * h // 8)]
        ratio = sum(p == (0, 0, 0) for p in edge) / len(edge)
    print(f'AMOLED black edge: {ratio:.3f}', flush=True)
    if ratio < .80:
        raise AssertionError('AMOLED canvas is not black')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial', required=True)
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not re.fullmatch(r'[0-9a-f]{64}', args.sha256) or hashlib.sha256(args.apk.read_bytes()).hexdigest() != args.sha256:
        raise ValueError('Preview APK digest mismatch')
    e = base.Emulator(args.serial, args.output)
    e.adb('shell', 'settings', 'put', 'global', 'animator_duration_scale', '1')
    e.install_and_start(args.apk)
    initial = e.dump('initial-home')
    assert 'PREVIEW ONLY' in e.all_text(initial), 'preview isolation must be visible'
    e.tap('Settings', 'open-settings')
    screenshots = {}
    styles = [('Pixel Signal', 'pixel'), ('Cyberpunk', 'cyberpunk'), ('iOS Glass', 'ios_glass'), ('Neon', 'neon')]
    for label, style_id in styles:
        choose(e, label, 'select-' + style_id)
        if f'<string name="manager_visual_style">{style_id}</string>' not in e.prefs():
            raise AssertionError(f'{style_id} selection was not saved')
        choose(e, 'Dark', 'dark-' + style_id)
        dark = e.screenshot('settings-dark-' + style_id)
        choose(e, 'Light', 'light-' + style_id)
        light = e.screenshot('settings-light-' + style_id)
        print(f'{label} brightness light={brightness(light):.1f} dark={brightness(dark):.1f}', flush=True)
        if brightness(light) < brightness(dark) + 35:
            raise AssertionError(f'{label} light and dark modes not distinct')
        choose(e, 'AMOLED black', 'amoled-' + style_id)
        assert_amoled_black(e.screenshot('settings-amoled-' + style_id))
        choose(e, 'Dark', 'dark-visual-' + style_id)
        e.tap('Home', 'home-' + style_id)
        screenshots[style_id] = e.screenshot('home-' + style_id)
        e.tap('Settings', 'return-settings-' + style_id)
        for _ in range(3):
            e.adb('shell', 'input', 'swipe', '540', '650', '540', '1600', '250')
        root = e.wait_for(label, 'verify-choice-' + style_id, scroll=True)
        e.assert_checked(root, label, True)
    for style_id in ('cyberpunk', 'ios_glass', 'neon'):
        delta = difference(screenshots['pixel'], screenshots[style_id])
        print(f'Home appearance difference pixel/{style_id}: {delta:.2f}', flush=True)
        if delta < 2.0:
            raise AssertionError(f'{style_id} did not visibly change the home screen')

    e.tap('Appearance motion', 'disable-motion', scroll=True)
    if '<boolean name="neon_motion" value="false"' not in e.prefs():
        raise AssertionError('Motion preference was not saved')
    saved = e.prefs()
    e.adb('shell', 'am', 'force-stop', base.PACKAGE)
    e.adb('shell', 'am', 'start', '-W', '-n', base.ACTIVITY)
    time.sleep(4)
    if e.prefs() != saved:
        raise AssertionError('Preferences changed after process restart')
    e.tap('Settings', 'settings-after-restart')
    root = e.wait_for('Neon', 'neon-after-restart', scroll=True)
    e.assert_checked(root, 'Neon', True)
    e.tap('Home', 'motion-off-home')
    time.sleep(2)
    first = e.screenshot('motion-off-1')
    time.sleep(1.5)
    second = e.screenshot('motion-off-2')
    delta = difference(first, second)
    print(f'Motion disabled screen difference: {delta:.5f}', flush=True)
    if delta > .05:
        raise AssertionError('Screen did not settle with appearance motion disabled')
    packages = e.adb('shell', 'pm', 'list', 'packages')
    if f'package:{base.PACKAGE}' not in packages or 'package:net.ember.labs\n' in packages:
        raise AssertionError('Expected only the isolated preview, not the real Manager')
    print('All four themes, light/dark/AMOLED and persistence passed in the non-root preview.', flush=True)


if __name__ == '__main__':
    main()
