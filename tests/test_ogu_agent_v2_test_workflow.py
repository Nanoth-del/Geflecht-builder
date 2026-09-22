"""The isolated public CI must never publish private source or an IPA."""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/ogu-agent-v2-tests-only.yml"
SOURCE_SHA = "8de53af4aa286064f08461e613607f3e05ef2f97"


def test_source_is_immutable_and_workflow_has_no_release_steps():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert SOURCE_SHA in content
    assert "runs-on: xcode-27" in content
    assert "CODE_SIGNING_ALLOWED=NO test" in content
    assert "secrets.OGUSUPPORT" in content
    assert "  push:" in content
    for banned in ("gh release", "release create", "upload-artifact", "git push", " xcodebuild archive", "GITHUB_TOKEN:"):
        assert banned not in content
