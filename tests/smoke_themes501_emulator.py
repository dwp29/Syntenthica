#!/usr/bin/env python3
"""Quick actual-screen smoke; simulated no-root fixture on an AVD only."""
import argparse
import time
from pathlib import Path
from run_themes501_emulator import (FixtureEmulator, base, check_home, choose, difference,
                                    require_hash, to_customize, to_home)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial', required=True)
    p.add_argument('--apk', required=True, type=Path)
    p.add_argument('--sha256', required=True)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    require_hash(a.apk, a.sha256)
    e = FixtureEmulator(a.serial, a.output)
    e.install_and_start(a.apk)
    check_home(e, e.dump('smoke-initial'), 'initial')
    shots = {}
    for label, style in [('Pixel Signal', 'pixel'), ('Cyberpunk', 'cyberpunk'), ('iOS Glass', 'ios_glass'), ('Neon', 'neon')]:
        to_customize(e, 'smoke-' + style)
        choose(e, label, 'smoke-choice-' + style)
        choose(e, 'Dark', 'smoke-dark-' + style)
        home = to_home(e, 'smoke-' + style, settings_screenshot=True)
        check_home(e, home, style)
        shots[style] = e.screenshot('smoke-home-' + style)
    for style in ('cyberpunk', 'ios_glass', 'neon'):
        delta = difference(shots['pixel'], shots[style])
        print(f'Actual Home difference pixel/{style}={delta:.2f}', flush=True)
        if delta < 3: raise AssertionError('Not visibly distinct on actual screen')
    print('Actual screen smoke passed using simulated data; no live root or phone was tested.', flush=True)


if __name__ == '__main__':
    main()
