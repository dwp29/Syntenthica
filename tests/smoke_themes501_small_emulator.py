#!/usr/bin/env python3
"""Target small-screen/large-font behavior in the isolated simulated AVD fixture."""
import argparse
from pathlib import Path

from run_themes501_emulator import (FixtureEmulator, choose, require_hash,
                                    test_small_screen, to_customize, to_home)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial', required=True)
    p.add_argument('--apk', required=True, type=Path)
    p.add_argument('--sha256', required=True)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    require_hash(args.apk, args.sha256)
    e = FixtureEmulator(args.serial, args.output)
    e.install_and_start(args.apk)
    # Match the comprehensive suite's state immediately before it resizes.
    to_customize(e, 'small-seed')
    choose(e, 'Neon', 'small-seed-neon')
    choose(e, 'Dark', 'small-seed-dark')
    if '<boolean name="neon_motion" value="false"' not in e.prefs():
        e.tap('Appearance motion', 'small-seed-motion', scroll=True)
    to_home(e, 'small-seed')
    styles = [('Pixel Signal', 'pixel'), ('Cyberpunk', 'cyberpunk'),
              ('iOS Glass', 'ios_glass'), ('Neon', 'neon')]
    test_small_screen(e, styles)
    print('Small-screen and large-font fixture scenarios passed. No physical device or root tested.', flush=True)


if __name__ == '__main__':
    main()
