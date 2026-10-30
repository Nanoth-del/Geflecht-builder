"""Publish counts/test identifiers/categories, never raw Xcode messages or logs."""
import json
from pathlib import Path
import re
import sys


def category(text):
    value = text.lower()
    if 'timed out' in value or 'timeout' in value: return 'timeout'
    if 'signal' in value or 'crashed' in value or 'killed:' in value: return 'process-crash'
    if 'unable to boot' in value or 'failed to boot' in value: return 'simulator-boot'
    if 'failed to launch' in value or 'could not launch' in value: return 'test-host-launch'
    if 'unable to find a destination' in value: return 'simulator-destination'
    if 'compiler' in value or 'compilation failed' in value: return 'compiler'
    if 'xctassert' in value or 'assertion' in value: return 'assertion'
    if 'cancelled' in value or 'canceled' in value: return 'cancelled'
    return 'unclassified'


def identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_./() -]{1,240}', value) else 'unreported-test'


def visit(node):
    if isinstance(node, list):
        for value in node: visit(value)
    elif isinstance(node, dict):
        message = node.get('failureText') or node.get('message') or node.get('issueType')
        name = node.get('testName') or node.get('testIdentifier') or node.get('testCaseName') or node.get('name')
        if isinstance(message, str):
            print('XCTest issue:', identifier(name), 'category='+category(message))
        if node.get('nodeType') == 'Test Case' and node.get('result') in ('Skipped', 'Failed'):
            print('XCTest case:', node['result'], identifier(name))
        for value in node.values(): visit(value)


for filename in sys.argv[1:]:
    path = Path(filename)
    if not path.is_file(): continue
    if path.suffix == '.log':
        print('XCTest log category:', category(path.read_text(encoding='utf-8', errors='replace')))
        continue
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        print('XCTest structured summary unavailable')
        continue
    if isinstance(data, dict):
        values = []
        for key in ('result', 'passedTests', 'failedTests', 'skippedTests', 'totalTestCount'):
            value = data.get(key)
            if isinstance(value, (int, float)) or (key == 'result' and value in ('Passed', 'Failed', 'Skipped', 'Unknown')):
                values.append(f'{key}={value}')
        if values: print('XCTest summary:', ', '.join(values))
    visit(data)
