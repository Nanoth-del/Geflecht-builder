"""Static regression tests for the private GeflechtEQ IPA packaging workflow."""
from pathlib import Path
import unittest

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github" / "workflows" / "build-ios-unsigned.yml"
)


class GeflechtEQIPAPackagingTests(unittest.TestCase):
    def test_standard_zip_and_crc_validation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        package = text.split("- name: Package unsigned IPA privately", 1)[1]
        package = package.split("- name: Audit unsigned IPA privately", 1)[0]
        self.assertIn('mkdir -p "$ipa_root/Payload"', package)
        self.assertIn('ditto "$app_path" "$ipa_root/Payload/$APP_NAME.app"', package)
        self.assertIn('/usr/bin/zip -q -r -X -y "$ipa_path" Payload', package)
        self.assertIn('unzip -Z1 "$ipa_path"', package)
        self.assertIn('unzip -tq "$ipa_path"', package)
        self.assertNotIn('ditto -c -k --sequesterRsrc', package)

    def test_privacy_audit_and_private_release_verification_retained(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("CODE_SIGNING_ALLOWED=NO", text)
        self.assertIn('if [[ -e "$app_path/_CodeSignature" ]]', text)
        self.assertIn('sha256', text)
        self.assertIn('--prerelease', text)
        self.assertIn('rm -f "$RUNNER_TEMP"/geflechteq-*.log', text)


if __name__ == "__main__":
    unittest.main()
