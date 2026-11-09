from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_synthetica40 as s40


class WorkDirectoryGuardTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
