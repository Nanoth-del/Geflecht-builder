"""Exercise the WAR public controller without credentials or network access."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/protected-war-ios.yml'


def steps():
    source = WORKFLOW.read_text(encoding='utf-8')
    result = {}
    for chunk in source.split('      - name: ')[1:]:
        name = chunk.splitlines()[0]
        if '        run: |\n' in chunk:
            result[name] = textwrap.dedent(chunk.split('        run: |\n', 1)[1])
    return result


class ProtectedWarBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        git_bash = Path('C:/Program Files/Git/bin/bash.exe')
        cls.bash = str(git_bash) if git_bash.is_file() else shutil.which('bash')
        if not cls.bash:
            raise AssertionError('Bash is required to verify the actual workflow blocks')

    def test_fixed_target_and_dispatch_contract(self):
        source = WORKFLOW.read_text(encoding='utf-8')
        trigger = source.split('\non:\n', 1)[1].split('\npermissions:', 1)[0]
        self.assertEqual(trigger.strip(), 'workflow_dispatch:')
        self.assertIn('permissions: {}', source)
        self.assertIn('runs-on: macos-15', source)
        self.assertIn('timeout-minutes: 70', source)
        self.assertIn('https://api.github.com/repositories/1431948260', source)
        secrets = re.findall(r'secrets\.([A-Za-z0-9_]+)', source)
        self.assertEqual(secrets, ['WAR', 'WAR', 'WAR'])
        self.assertNotRegex(source, r'(?i)actions/(?:upload-artifact|cache|checkout)')
        self.assertNotIn('source_ref', source)
        self.assertNotRegex(source, r'\b[0-9a-f]{40}\b(?!\n        with:)')
        checkout = steps()['Obtain protected source']
        self.assertIn('fetch --depth=1 --no-tags origin "$revision"', checkout)
        self.assertNotIn('origin main', checkout)
        self.assertIn("jq -r '.private'", checkout)
        self.assertIn('::add-mask::$repo" >&3', checkout)
        self.assertIn('::add-mask::$revision" >&3', checkout)
        self.assertIn('::add-mask::$auth" >&3', checkout)

    def test_compile_has_no_token_or_version_override(self):
        source = WORKFLOW.read_text(encoding='utf-8')
        compile_step = source.split('      - name: Compile and privacy-audit\n', 1)[1].split('      - name:', 1)[0]
        self.assertIn('OUTPUT_DIR: ${{ runner.temp }}/private-output', compile_step)
        self.assertIn('BUILDER_REVISION: ${{ github.sha }}', compile_step)
        self.assertNotIn('TOKEN', compile_step)
        self.assertNotIn('BUILD_NUMBER', compile_step)
        self.assertNotIn('run_number', compile_step)

    def test_all_bash_blocks_parse(self):
        for name, body in steps().items():
            with self.subTest(step=name):
                result = subprocess.run([self.bash, '-n'], input=body, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_compile_failure_withholds_private_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix='war-private-') as temp:
            scratch = Path(temp)
            script = scratch / 'private-src/.ci/build-unsigned.sh'
            script.parent.mkdir(parents=True)
            script.write_text("#!/bin/bash\nprintf 'WAR_PRIVATE_STDOUT_SENTINEL\\n'\nprintf 'error: WAR_PRIVATE_STDERR_SENTINEL /private/source/path\\n' >&2\nexit 42\n", encoding='utf-8')
            env = os.environ.copy()
            env.update(RUNNER_TEMP=str(scratch), OUTPUT_DIR=str(scratch / 'private-output'), BUILDER_REVISION='controller-test')
            result = subprocess.run([self.bash, '-c', steps()['Compile and privacy-audit']], env=env,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 1)
            self.assertIn('diagnostics withheld', result.stdout)
            self.assertEqual(result.stderr, '')
            self.assertNotIn('WAR_PRIVATE_', result.stdout + result.stderr)
            log = (scratch / 'private-build.log').read_text(encoding='utf-8')
            self.assertIn('WAR_PRIVATE_STDOUT_SENTINEL', log)
            self.assertIn('WAR_PRIVATE_STDERR_SENTINEL', log)

    def test_release_verifies_every_asset_before_and_after_publication(self):
        body = steps()['Publish verified private Release']
        self.assertIn('--prerelease --draft', body)
        self.assertIn('--target "$revision"', body)
        self.assertIn('gh release download "$tag" --repo "$repo" --dir "$destination"', body)
        self.assertIn('cmp "$output/SHA256SUMS.txt" "$destination/SHA256SUMS.txt"', body)
        self.assertIn('cmp "$asset" "$destination/$(basename "$asset")"', body)
        self.assertIn('shasum -a 256 -c SHA256SUMS.txt', body)
        before = body.index('verify_release "$RUNNER_TEMP/private-verify/draft"')
        publish = body.index('--draft=false')
        after = body.index('verify_release "$RUNNER_TEMP/private-verify/published"')
        self.assertLess(before, publish)
        self.assertLess(publish, after)
        self.assertIn('private-war-build-$GITHUB_RUN_NUMBER-$GITHUB_RUN_ATTEMPT-$short', body)
        self.assertIn('>"$RUNNER_TEMP/private-release.log" 2>&1', body)

    def test_failure_and_cleanup_contract(self):
        source = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('if: failure()', source)
        self.assertIn('if: always()', source)
        failure = steps()['Preserve failure diagnostics privately']
        for asset in ('build-failure.json', 'private-diagnostics.zip', 'private-build.log'):
            self.assertIn(asset, failure)
        self.assertIn('--prerelease --draft', failure)
        cleanup = steps()['Erase temporary private material']
        for name in ('private-src', 'private-output', 'private-derived', 'private-stage', 'private-audit',
                     'private-verify', 'private-repo', 'private-revision', 'private-*.log'):
            self.assertIn(name, cleanup)


if __name__ == '__main__':
    unittest.main()
