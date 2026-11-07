#!/usr/bin/env python3
"""Runtime Boost tests. All proc, mixer, Wi-Fi and service paths are fakes."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'build-kit/ci/ksun-pixel40/assets/synthetica-boost40.sh'
BOOT = '11111111-1111-1111-1111-111111111111'


class PixelBoostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix='pixel40-boost-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.proc = self.root / 'proc'
        self.state = self.root / 'state'
        self.service = self.root / 'service.d'
        self.bin = self.root / 'bin'
        self.audio = self.root / 'audio'
        self.wifi = self.root / 'wifi'
        self.bin.mkdir()
        self.audio.mkdir()
        self.service.mkdir()
        self.executable('id', "#!/bin/sh\necho \"${FAKE_UID:-0}\"\n")
        self.executable('iw', '''#!/bin/sh
if [ "$*" = 'dev wlan0 get power_save' ]; then echo "Power save: $(cat "$IW_STATE")"; exit; fi
if [ "$1 $2 $3 $4" = 'dev wlan0 set power_save' ]; then echo "$5" > "$IW_STATE"; exit; fi
exit 1
''')
        self.executable('tinymix', '''#!/bin/sh
style=${TINYMIX_STYLE:-value}
if [ "$1" = -v ]; then
    if [ "$style" = value ]; then ctl=$2; mode=read
    elif [ "$style" = modern ]; then echo 'tinymix version 2.0'; exit 0
    else exit 1; fi
elif [ "$1" = get ]; then
    [ "$style" = modern ] || exit 1
    ctl=$2; mode=read
elif [ "$1" = set ]; then
    [ "$style" = modern ] || exit 1
    ctl=$2; mode=write; wanted=$3
elif [ "$#" = 1 ]; then
    [ "$style" = legacy ] || exit 1
    ctl=$1; mode=read
elif [ "$#" = 2 ]; then
    [ "$style" != modern ] || exit 1
    ctl=$1; mode=write; wanted=$2
else exit 1; fi
case "$ctl" in 'RX0 Digital Volume') path="$TINYMIX_DIR/rx0" ;; 'RX1 Digital Volume') path="$TINYMIX_DIR/rx1" ;; 'RX2 Digital Volume') path="$TINYMIX_DIR/rx2" ;; *) exit 1 ;; esac
[ -f "$path" ] || exit 1
if [ "$mode" = write ]; then echo "$wanted $wanted" > "$path"; exit; fi
case "$style" in
    value) cat "$path" ;;
    legacy) echo "$ctl: $(cat "$path") (range 0->124)" ;;
    modern) printf '%s (range 0->124)\\n' "$(sed 's/ /, /g' "$path")" ;;
esac
''')
        for rel, value in {
            'sys/kernel/random/boot_id': BOOT,
            'sys/net/core/rmem_max': '262144',
            'sys/net/core/wmem_max': '262144',
            'sys/net/ipv4/tcp_fastopen': '1',
            'sys/net/core/default_qdisc': 'pfifo_fast',
            'sys/net/ipv4/tcp_congestion_control': 'cubic',
            'sys/net/ipv4/tcp_available_congestion_control': 'cubic bbr',
        }.items():
            self.put(self.proc / rel, value)
        for name, value in {'rx0': '73 73', 'rx1': '78 78', 'rx2': '81 81'}.items():
            self.put(self.audio / name, value)
        self.put(self.wifi, 'on')
        self.env = dict(os.environ, SP_PROCSYS=str(self.proc), SP_STATE_DIR=str(self.state),
                        SP_SERVICE_DIR=str(self.service), TINYMIX_DIR=str(self.audio), IW_STATE=str(self.wifi),
                        PATH=f'{self.bin}:{os.environ["PATH"]}')

    def executable(self, name: str, contents: str) -> None:
        path = self.bin / name
        path.write_text(contents)
        path.chmod(0o755)

    @staticmethod
    def put(path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value + '\n')

    @staticmethod
    def read(path: Path) -> str:
        return path.read_text().strip()

    def run_boost(self, action: str, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(['sh', str(SCRIPT), action], env={**self.env, **extra},
                              capture_output=True, text=True, timeout=15, check=False)

    def test_network_snapshots_every_changed_value_and_restores_them(self) -> None:
        result = self.run_boost('network_apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('verified=6 skipped=0 failed=0', result.stdout)
        self.assertEqual(self.read(self.proc / 'sys/net/core/rmem_max'), '8388608')
        self.assertEqual(self.read(self.proc / 'sys/net/ipv4/tcp_congestion_control'), 'bbr')
        self.assertEqual(self.read(self.wifi), 'off')
        self.assertEqual(list(self.service.iterdir()), [], '4.0 must never install a boot script')
        result = self.run_boost('network_restore')
        self.assertEqual(result.returncode, 0, result.stdout)
        for rel, value in {'sys/net/core/rmem_max': '262144', 'sys/net/core/wmem_max': '262144',
                           'sys/net/ipv4/tcp_fastopen': '1', 'sys/net/core/default_qdisc': 'pfifo_fast',
                           'sys/net/ipv4/tcp_congestion_control': 'cubic'}.items():
            self.assertEqual(self.read(self.proc / rel), value)
        self.assertEqual(self.read(self.wifi), 'on')
        self.assertFalse(list((self.state / BOOT / 'network').glob('*.orig')))

    def test_audio_originals_are_restored_not_a_hardcoded_gain(self) -> None:
        for style in ('value', 'legacy', 'modern'):
            with self.subTest(style=style):
                apply = self.run_boost('audio_apply:92', TINYMIX_STYLE=style)
                self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
                self.assertEqual(self.read(self.audio / 'rx0'), '92 92')
                # Reapplying a different level keeps the very first original.
                self.assertEqual(self.run_boost('audio_apply:96', TINYMIX_STYLE=style).returncode, 0)
                restore = self.run_boost('audio_restore', TINYMIX_STYLE=style)
                self.assertEqual(restore.returncode, 0, restore.stdout)
                self.assertEqual(self.read(self.audio / 'rx0'), '73 73')
                self.assertEqual(self.read(self.audio / 'rx1'), '78 78')
                self.assertEqual(self.read(self.audio / 'rx2'), '81 81')

    def test_different_mixer_channels_are_not_modified(self) -> None:
        self.put(self.audio / 'rx1', '51 70')
        result = self.run_boost('audio_apply:88')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SKIPPED: rx1', result.stdout)
        self.assertEqual(self.read(self.audio / 'rx1'), '51 70')
        self.assertFalse((self.state / BOOT / 'audio/rx1.orig').exists())
        self.assertEqual(self.run_boost('audio_restore').returncode, 0)

    def test_external_change_is_never_overwritten(self) -> None:
        self.assertEqual(self.run_boost('network_apply').returncode, 0)
        node = self.proc / 'sys/net/core/rmem_max'
        self.put(node, '123456')
        again = self.run_boost('network_apply')
        self.assertNotEqual(again.returncode, 0)
        self.assertIn('rmem changed externally; not overwritten', again.stdout)
        restore = self.run_boost('network_restore')
        self.assertNotEqual(restore.returncode, 0)
        self.assertIn('rmem changed externally; not overwritten', restore.stdout)
        self.assertEqual(self.read(node), '123456')
        self.assertTrue((self.state / BOOT / 'network/rmem.orig').exists())
        self.assertEqual(self.read(self.proc / 'sys/net/core/wmem_max'), '262144')

    def test_partial_and_unreadable_targets_are_reported(self) -> None:
        (self.proc / 'sys/net/core/rmem_max').unlink()
        self.put(self.proc / 'sys/net/ipv4/tcp_available_congestion_control', 'cubic')
        result = self.run_boost('network_apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SKIPPED: rmem', result.stdout)
        self.assertIn('SKIPPED: bbr', result.stdout)
        self.assertIn('skipped=2', result.stdout)
        self.assertEqual(self.run_boost('network_restore').returncode, 0)

    def test_new_boot_never_restores_old_snapshot(self) -> None:
        self.assertEqual(self.run_boost('network_apply').returncode, 0)
        self.put(self.proc / 'sys/kernel/random/boot_id', '22222222-2222-2222-2222-222222222222')
        result = self.run_boost('network_restore')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('RESTORED:', result.stdout)
        self.assertEqual(self.read(self.proc / 'sys/net/core/rmem_max'), '8388608')

    def test_root_action_and_snapshot_guards(self) -> None:
        before = self.read(self.proc / 'sys/net/core/rmem_max')
        for action in ('audio_apply:97', 'audio_apply:88;touch /tmp/evil', 'network_apply;id', 'invalid'):
            self.assertNotEqual(self.run_boost(action).returncode, 0)
        self.assertNotEqual(self.run_boost('network_apply', FAKE_UID='2000').returncode, 0)
        self.assertEqual(self.read(self.proc / 'sys/net/core/rmem_max'), before)
        self.state.mkdir()
        (self.state / f'lock-{BOOT}').mkdir()
        locked = self.run_boost('network_apply')
        self.assertNotEqual(locked.returncode, 0)
        self.assertIn('another Boost action', locked.stdout)
        self.assertEqual(self.read(self.proc / 'sys/net/core/rmem_max'), before)

    def test_symlinked_state_or_snapshot_is_rejected(self) -> None:
        outside = self.root / 'outside'
        outside.mkdir()
        self.state.symlink_to(outside, target_is_directory=True)
        result = self.run_boost('network_apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.state.unlink()
        snap = self.state / BOOT / 'network'
        snap.mkdir(parents=True)
        (snap / 'rmem.orig').symlink_to(outside / 'victim')
        result = self.run_boost('network_apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('rmem snapshot is a symlink', result.stdout)
        self.assertFalse((outside / 'victim').exists())
        self.assertEqual(self.read(self.proc / 'sys/net/core/rmem_max'), '262144')

    def test_old_scripts_are_detected_then_removed_only_on_explicit_request(self) -> None:
        for name in ('synthetica-boost.sh', 'rc-boost.sh', 'synthetica-sound.sh', 'rc-sound.sh', 'unrelated.sh'):
            self.put(self.service / name, '# fake')
        status = self.run_boost('status')
        self.assertEqual(status.returncode, 0)
        self.assertEqual(status.stdout.count('LEGACY STARTUP PRESENT:'), 4)
        self.assertEqual(len(list(self.service.iterdir())), 5)
        self.assertFalse(self.state.exists(), 'status is read-only')
        removed = self.run_boost('remove_legacy')
        self.assertEqual(removed.returncode, 0, removed.stdout)
        self.assertEqual([p.name for p in self.service.iterdir()], ['unrelated.sh'])
        self.assertIn('not inferred or restored', removed.stdout)

    def test_symlinked_service_dir_cannot_delete_files(self) -> None:
        target = self.root / 'elsewhere'
        target.mkdir()
        self.put(target / 'rc-boost.sh', 'do not delete')
        self.service.rmdir()
        self.service.symlink_to(target, target_is_directory=True)
        self.assertNotEqual(self.run_boost('remove_legacy').returncode, 0)
        self.assertTrue((target / 'rc-boost.sh').exists())


if __name__ == '__main__':
    unittest.main()
