"""An archive failure must keep its detailed diagnostic in the runner file."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PrivateBuildLogOutputTests(unittest.TestCase):
    def test_archive_failure_does_not_publish_diagnostic(self):
        source = (ROOT/'.github/workflows/build-ios-unsigned.yml').read_text(encoding='utf-8')
        step = source.split('      - name: Build fresh unsigned archive privately\n', 1)[1]
        body = textwrap.dedent(step.split('        run: |\n', 1)[1].split('\n      - name:', 1)[0])
        git_bash = Path('C:/Program Files/Git/bin/bash.exe')
        shell = str(git_bash) if git_bash.is_file() else shutil.which('bash')
        self.assertIsNotNone(shell, 'Bash is required to exercise the real workflow step')
        build = ROOT/'build'
        build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='private-log-', dir=build) as temp:
            scratch = Path(temp).resolve()
            # The real step removes only this scratch archive path.
            archive = (scratch/'GeflechtEQ.xcarchive').resolve()
            self.assertTrue(archive.is_relative_to(scratch))
            env = os.environ.copy()
            env.update(RUNNER_TEMP=str(scratch), BUILD_NUMBER='999', APP_NAME='GeflechtEQ',
                       PROJECT_PATH='GeflechtEQ.xcodeproj', SCHEME='GeflechtEQ')
            prefix = "xcodebuild() { printf 'error: PRIVATE_BUILD_DIAGNOSTIC_SENTINEL\\n' >&2; return 1; }\n"
            result = subprocess.run([shell, '-c', prefix+body], env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 1)
            self.assertIn('iOS archive failed.', result.stdout)
            self.assertNotIn('PRIVATE_BUILD_DIAGNOSTIC_SENTINEL', result.stdout+result.stderr,
                             'Detailed private diagnostic reached the public console')
            self.assertIn('PRIVATE_BUILD_DIAGNOSTIC_SENTINEL',
                          (scratch/'geflechteq-xcodebuild.log').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
