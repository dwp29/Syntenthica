from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_synthetica40 as s40
import collect_synthetica40 as collector


class WorkDirectoryGuardTests(unittest.TestCase):
    def test_ksun_syscall_hook_requires_real_tracepoints(self):
        config = s40.parse_config(ROOT / 'build-kit/ci/synthetica40/experimental.config')
        for symbol in ('CONFIG_KPROBES', 'CONFIG_FTRACE', 'CONFIG_FTRACE_SYSCALLS',
                       'CONFIG_TRACEPOINTS', 'CONFIG_KSU'):
            self.assertEqual(config.get(symbol), 'y', symbol)

    def test_ci_scratch_can_be_inside_home_but_not_home_itself(self):
        with tempfile.TemporaryDirectory(prefix='.s40-guard-', dir=Path.home()) as temp:
            source = Path(temp) / 'inputs' / 'kernel'
            source.mkdir(parents=True)
            # GitHub RUNNER_TEMP is inside /home/runner. It is a sibling of the
            # repository and inputs, not an ancestor or descendant of either.
            s40.check_work_directory(Path(temp) / 'work', [source])
            with self.assertRaises(ValueError):
                s40.check_work_directory(Path.home(), [source])
            with self.assertRaises(ValueError):
                s40.check_work_directory(source / 'work', [source])
            with self.assertRaises(ValueError):
                s40.check_work_directory(Path(temp), [source])

    def test_collector_rejects_missing_tracepoints_before_export(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            out = base / 'out'
            out.mkdir()
            # Earlier requirements are present, but the syscall hook's actual
            # tracepoint is absent. No evidence directory should be produced.
            (out / '.config').write_text(
                'CONFIG_KSU=y\nCONFIG_NOMOUNT=y\nCONFIG_KPROBES=y\n'
                '# CONFIG_FTRACE_SYSCALLS is not set\nCONFIG_TRACEPOINTS=y\n')
            destination = base / 'evidence'
            with self.assertRaisesRegex(ValueError, 'CONFIG_FTRACE_SYSCALLS'):
                collector.collect(out, base / 'modules', base / 'nm', destination, {})
            self.assertFalse(destination.exists())


class BuildPipelineTests(unittest.TestCase):
    def run_fake_build(self, fail_selinux: bool):
        with tempfile.TemporaryDirectory(prefix='s40-fake-build-') as temp:
            base = Path(temp)
            src, out, modules, bindir = (base / name for name in ('src', 'out', 'modules', 'bin'))
            for directory in ('drivers/kernelsu', 'fs/nomount', 'arch/arm64',
                              'scripts/kconfig', 'miatoll/configs'):
                (src / directory).mkdir(parents=True, exist_ok=True)
            (src / 'drivers/kernelsu/Kbuild').write_text('')
            (src / 'fs/nomount/nomount.c').write_text('')
            (src / 'arch/arm64/Kconfig.platforms').write_text('config ARCH_QCOM\n')
            for name in ('sm7125-prune', 'miatoll', 'lineage1'):
                (src / 'miatoll/configs' / (name + '.config')).write_text('')
            merge = src / 'scripts/kconfig/merge_config.sh'
            merge.write_text('#!/bin/bash\nset -e\nout=$3\nshift 4\n'
                             'for fragment in "$@"; do cat "$fragment" >> "$out/.config"; done\n')
            merge.chmod(0o755)
            bindir.mkdir()
            fake_make = bindir / 'make'
            fake_make.write_text('''#!/bin/bash
set -e
printf '%s\\n' "$*" >> "$S40_FAKE_LOG"
for arg in "$@"; do
  case "$arg" in O=*) out=${arg#O=} ;; esac
done
case " $* " in
  *" defconfig "*) mkdir -p "$out"; printf '# CONFIG_FAKE is not set\\n' > "$out/.config" ;;
  *" security/selinux/ "*) if [[ ${S40_FAKE_FAIL_SELINUX:-0} == 1 ]]; then exit 66; fi ;;
esac
''')
            fake_make.chmod(0o755)
            env = os.environ.copy()
            env.pop('S40_CONFIG_ONLY', None)
            env.update(S40_SOURCE=str(src), S40_OUT=str(out), S40_MODULES=str(modules),
                       S40_JOBS='2', S40_FAKE_LOG=str(base / 'make.log'),
                       S40_FAKE_FAIL_SELINUX='1' if fail_selinux else '0',
                       PATH=str(bindir) + os.pathsep + env.get('PATH', ''))
            result = subprocess.run(['bash', str(ROOT / 'build-kit/scripts/build_synthetica40_kernel.sh')],
                                    env=env, capture_output=True, text=True)
            calls = (base / 'make.log').read_text().splitlines()
            return result, calls

    def test_selinux_prebuild_precedes_parallel_kernel_and_modules(self):
        result, calls = self.run_fake_build(fail_selinux=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prebuild = next(i for i, call in enumerate(calls) if 'security/selinux/' in call)
        compile_ = next(i for i, call in enumerate(calls) if 'Image dtbs modules' in call)
        install = next(i for i, call in enumerate(calls) if 'modules_install' in call)
        self.assertLess(prebuild, compile_)
        self.assertLess(compile_, install)

    def test_failing_selinux_prebuild_stops_kernel_build(self):
        result, calls = self.run_fake_build(fail_selinux=True)
        self.assertEqual(result.returncode, 66, result.stderr + result.stdout)
        self.assertTrue(any('security/selinux/' in call for call in calls))
        self.assertFalse(any('Image dtbs modules' in call or 'modules_install' in call for call in calls))


if __name__ == '__main__':
    unittest.main()
