from pathlib import Path
import unittest

WORKFLOW = (Path(__file__).resolve().parents[1] / '.github' /
            'workflows' / 'build-geflechtboard.yml')

class KeyboardExtensionAuditTests(unittest.TestCase):
    def test_inspects_installable_keyboard_extension_inside_ipa(self):
        workflow = WORKFLOW.read_text(encoding='utf-8')
        audit = workflow.split('- name: Audit unsigned IPA privately', 1)[1]
        audit = audit.split('- name: Publish and verify private Release asset', 1)[0]
        for required in ('PlugIns/GeflechtBoardKeyboard.appex',
                         'Print :CFBundleExecutable', 'Print :CFBundleName',
                         'Print :CFBundlePackageType', 'Print :CFBundleIdentifier',
                         'Print :NSExtension:NSExtensionPointIdentifier',
                         '"$extension_path/$extension_executable"', 'otool -hv'):
            self.assertIn(required, audit)
        self.assertIn('GeflechtBoardKeyboard', audit)
        self.assertIn('XPC!', audit)

if __name__ == '__main__':
    unittest.main()
