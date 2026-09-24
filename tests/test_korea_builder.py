from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'build-korea.yml'

class KoreaBuilderTests(unittest.TestCase):
    def test_korea_workflow_is_pinned_and_private(self):
        source = WORKFLOW.read_text(encoding='utf-8')
        for expected in ['Nanoth-del/Korea', 'secrets.KOREA',
                         'SOURCE_REF', 'ios/App/App.xcodeproj', 'SCHEME: App',
                         'APP_NAME: App', 'RELEASE_REPOSITORY: Nanoth-del/Korea']:
            self.assertIn(expected, source)
        self.assertNotIn('SOURCE_REPOSITORY: ${{ inputs.', source)
        self.assertNotIn('RELEASE_REPOSITORY: ${{ inputs.', source)

    def test_generates_capacitor_ios_project_and_skips_xctest(self):
        source = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('npm ci', source)
        self.assertIn('npm run sync:ios', source)
        self.assertIn('KananaPlugin.swift', source)
        self.assertIn('CODE_SIGNING_ALLOWED=NO', source)
        self.assertNotIn('xcodebuild test', source)
        self.assertIn('gh release create', source)
        self.assertIn('SHA256', source.upper())

if __name__ == '__main__':
    unittest.main()
