from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'build-geflechtboard.yml'

class BoardBuilderTests(unittest.TestCase):
    def test_board_workflow_is_pinned_and_private(self):
        source = WORKFLOW.read_text(encoding='utf-8')
        for expected in ['Nanoth-del/GeflechtBoard', 'secrets.GeflechtBoard',
                         'SOURCE_REF', 'GeflechtBoard.xcodeproj', 'SCHEME: GeflechtBoard',
                         'APP_NAME: GeflechtBoard', 'RELEASE_REPOSITORY: Nanoth-del/GeflechtBoard']:
            self.assertIn(expected, source)
        self.assertNotIn('SOURCE_REPOSITORY: ${{ inputs.', source)
        self.assertNotIn('RELEASE_REPOSITORY: ${{ inputs.', source)

    def test_generates_xcode_project_and_skips_xctest(self):
        source = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('xcodegen generate', source)
        self.assertIn('xcode-27', source)
        self.assertIn('CODE_SIGNING_ALLOWED=NO', source)
        self.assertNotIn('xcodebuild test', source)
        self.assertIn('gh release create', source)
        self.assertIn('SHA-256', source)

if __name__ == '__main__':
    unittest.main()
