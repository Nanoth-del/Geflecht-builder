import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.github/scripts/ogu-xctest-summary.py'


def run_summary(data):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'summary.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True, timeout=10)


def test_reports_failure_category_without_private_message_values():
    message = '/Users/private-source/Secret.swift: PRIVATE_SOURCE_SENTINEL crashed with signal 6 ' + 'gh' + 'p_' + 'x' * 30
    result = run_summary({'result': 'Failed', 'passedTests': 4, 'failedTests': 1, 'testFailures': [{'testName': 'ToolTests/testCall()', 'failureText': message}]})
    assert result.returncode == 0
    assert 'passedTests=4' in result.stdout
    assert 'ToolTests/testCall()' in result.stdout
    assert 'process-crash' in result.stdout
    assert 'PRIVATE_SOURCE_SENTINEL' not in result.stdout
    assert '/Users/' not in result.stdout
    assert 'x' * 30 not in result.stdout


def test_reports_skipped_native_test_without_calling_it_passed():
    result = run_summary({'result': 'Passed', 'passedTests': 5, 'skippedTests': 1, 'testNodes': [{'nodeType': 'Test Case', 'name': 'testNativeCall()', 'result': 'Skipped'}]})
    assert result.returncode == 0
    assert 'skippedTests=1' in result.stdout
    assert 'Skipped testNativeCall()' in result.stdout
