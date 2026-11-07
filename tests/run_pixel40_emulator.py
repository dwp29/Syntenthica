#!/usr/bin/env python3
"""Exercise only the isolated 4.0 preview on an explicitly verified emulator.

No root Manager is installed, no root permissions are granted, and every Boost
or Control action is a simulation. The preview has no network access.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
from pathlib import Path
import re
import sys
import time

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_neon31_emulator as base

base.PACKAGE = 'net.ember.labs.pixel40preview'
base.ACTIVITY = f'{base.PACKAGE}/com.rifsxd.ksunext.PreviewActivity'


def mean_brightness(path: Path) -> float:
    with Image.open(path) as image:
        return ImageStat.Stat(image.convert('L')).mean[0]


def screen_difference(a: Path, b: Path) -> float:
    with Image.open(a) as first, Image.open(b) as second:
        w, h = first.size
        # Avoid status/nav bars (clock and system indicators); UI itself is static.
        rect = (0, h // 10, w, h * 9 // 10)
        delta = ImageChops.difference(first.convert('RGB').crop(rect), second.convert('RGB').crop(rect))
        return sum(ImageStat.Stat(delta).mean) / 3


def back(emulator: base.Emulator) -> None:
    emulator.adb('shell', 'input', 'keyevent', '4')
    time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{64}', args.sha256) or hashlib.sha256(args.apk.read_bytes()).hexdigest() != args.sha256:
        raise ValueError('Preview APK SHA-256 mismatch')
    e = base.Emulator(args.serial, args.output)
    e.adb('shell', 'settings', 'put', 'global', 'animator_duration_scale', '1')
    e.install_and_start(args.apk)
    home = e.dump('home')
    assert 'PREVIEW ONLY' in e.all_text(home), 'Must disclose preview isolation'
    e.screenshot('home')

    # Simulated diagnostics: the labels explicitly describe indicators, not proof.
    e.tap('Root diagnostics', 'open-diagnostics', scroll=True)
    e.wait_for('Support query', 'diagnostics-support')
    e.tap('Refresh diagnostics', 'diagnostics-refresh')
    diag = e.wait_for('Manager process flag', 'diagnostics-provider', scroll=True)
    assert 'Not reported in this process' in e.all_text(diag)
    e.wait_for('Possible conflict: multiple known providers are marked enabled. Verify before making changes.',
               'diagnostics-conflict', scroll=True)
    e.screenshot('diagnostics')
    back(e)

    # Applying a profile requires a confirmation. Here the callback is inert.
    e.tap('Synthetica Control', 'open-control', scroll=True)
    e.tap('Apply Gaming', 'control-gaming', scroll=True)
    dialog = e.wait_for('Confirm root action?', 'control-confirm')
    assert 'Gaming' in e.all_text(dialog)
    e.screenshot('control-confirm')
    e.tap('Continue', 'control-confirm-continue')
    result = e.wait_for('PREVIEW ONLY: simulated profile_gaming. No shell or settings changed.', 'control-simulated')
    assert 'Incomplete or unavailable' in e.all_text(result)
    e.tap('Close', 'control-result-close')
    back(e)

    e.tap('Network & audio Boost', 'open-boost', scroll=True)
    e.tap('Apply network Boost', 'boost-network', scroll=True)
    e.wait_for('Confirm root action?', 'boost-confirm')
    e.tap('Continue', 'boost-confirm-continue')
    e.wait_for('PREVIEW ONLY: simulated network_apply. No shell or settings changed.', 'boost-simulated')
    e.tap('Close', 'boost-result-close')
    back(e)

    # Catalog links never open until confirmation; preview handler never opens them at all.
    e.tap('Modules', 'modules-tab')
    e.tap('Popular sources & channels', 'open-sources')
    e.tap('LSPosed', 'lsposed', scroll=True)
    source = e.wait_for('Open an external source?', 'lsposed-confirm')
    assert 'https://github.com/LSPosed/LSPosed/releases' in e.all_text(source)
    assert 'Nothing is downloaded or installed' in e.all_text(source)
    e.screenshot('lsposed-confirm')
    e.tap('Cancel', 'lsposed-cancel')
    e.tap('Hide My Applist', 'hma', scroll=True)
    source = e.wait_for('Open an external source?', 'hma-confirm')
    assert 'APK' in e.all_text(source), 'Xposed APK should be distinguished from a module ZIP'
    e.tap('Cancel', 'hma-cancel')
    back(e)

    # Real theme choices and persisted preference, on an unprivileged preview.
    e.tap('Settings', 'settings')
    e.choose_radio('Light', 'settings-light')
    light = e.screenshot('settings-light')
    e.choose_radio('Dark', 'settings-dark')
    dark = e.screenshot('settings-dark')
    luma_light, luma_dark = mean_brightness(light), mean_brightness(dark)
    print(f'Appearance brightness: light={luma_light:.1f}, dark={luma_dark:.1f}', flush=True)
    assert luma_light > luma_dark + 40, 'Light/dark appearance did not change'
    e.choose_radio('AMOLED black', 'settings-amoled')
    amoled = e.screenshot('settings-amoled')
    with Image.open(amoled) as image:
        pix = image.convert('RGB')
        w, h = pix.size
        edge = [pix.getpixel((x, y)) for x in (1, w - 2) for y in range(h // 8, 7 * h // 8)]
        ratio = sum(p == (0, 0, 0) for p in edge) / len(edge)
    print(f'AMOLED black outer edge ratio: {ratio:.3f}', flush=True)
    assert ratio >= .80, 'AMOLED should leave the canvas black'

    # Explicit app setting disables ambient signals; disabled system scale does too.
    e.tap('Pixel motion', 'settings-motion-off', scroll=True)
    assert '<boolean name="neon_motion" value="false"' in e.prefs(), 'Pixel motion choice was not persisted'
    e.tap('Home', 'motion-off-home')
    time.sleep(2)
    off1 = e.screenshot('motion-off-1')
    time.sleep(1.5)
    off2 = e.screenshot('motion-off-2')
    off_delta = screen_difference(off1, off2)
    print(f'App motion off mean pixel difference: {off_delta:.5f}', flush=True)
    assert off_delta < .05, 'App motion off did not settle'
    e.tap('Settings', 'motion-on-settings')
    e.tap('Pixel motion', 'settings-motion-on', scroll=True)
    assert '<boolean name="neon_motion" value="true"' in e.prefs()
    e.adb('shell', 'settings', 'put', 'global', 'animator_duration_scale', '0')
    e.adb('shell', 'am', 'force-stop', base.PACKAGE)
    e.adb('shell', 'am', 'start', '-W', '-n', base.ACTIVITY)
    time.sleep(3)
    sys1 = e.screenshot('system-motion-off-1')
    time.sleep(1.5)
    sys2 = e.screenshot('system-motion-off-2')
    sys_delta = screen_difference(sys1, sys2)
    print(f'System animation scale 0 mean pixel difference: {sys_delta:.5f}', flush=True)
    assert sys_delta < .05, 'System animation disable was not respected'

    # The preview is not signed as or installed over the actual Manager.
    packages = e.adb('shell', 'pm', 'list', 'packages')
    assert f'package:{base.PACKAGE}' in packages
    assert 'package:net.ember.labs\n' not in packages
    print('4.0 preview emulator checks passed; real Manager/root/device tuning not tested.', flush=True)


if __name__ == '__main__':
    main()
