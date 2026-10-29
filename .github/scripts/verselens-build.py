"""Fixed-contract private-source builder. Never prints private tool output."""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

SOURCE_REPO = "Nanoth-del/VerseLens"
API = "https://api.github.com"
REF = os.environ.get("SOURCE_REF", "")
RUN = os.environ["GITHUB_RUN_ID"]
NUMBER = os.environ["GITHUB_RUN_NUMBER"]
ATTEMPT = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
TEMP = Path(os.environ["RUNNER_TEMP"]).resolve()
ROOT = (TEMP / f"verselens-{RUN}-{ATTEMPT}").resolve()
assert ROOT.is_relative_to(TEMP) and ROOT != TEMP
SOURCE = ROOT / "private-source"
LOGS = ROOT / "logs"
OUTPUT = ROOT / "output"


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if urllib.parse.urlparse(req.full_url).hostname != urllib.parse.urlparse(newurl).hostname:
            redirected.remove_header("Authorization")
        return redirected


def api(path, method="GET", body=None, binary=False, content_type=None, accept="application/vnd.github+json"):
    token = os.environ.get("PRIVATE_SOURCE_TOKEN")
    if not token:
        raise RuntimeError("Private source credential unavailable")
    headers = {"Authorization": "Bearer " + token, "Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    if content_type:
        headers["Content-Type"] = content_type
    payload = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
    url = path if path.startswith("https://") else API + path
    request = urllib.request.Request(url, data=payload, method=method, headers=headers)
    with urllib.request.build_opener(SafeRedirect()).open(request, timeout=120) as response:
        data = response.read()
    return data if binary else json.loads(data) if data else None


def validate_ref():
    if re.fullmatch(r"[0-9a-f]{40}", REF) is None:
        raise RuntimeError("Invalid immutable source reference")


def command(name, arguments, cwd=SOURCE, allow_failure=False):
    print(name + ": started (detailed output stays private).", flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment.pop("PRIVATE_SOURCE_TOKEN", None)
    environment.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    with (LOGS / (name + ".log")).open("wb") as log:
        result = subprocess.run(arguments, cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT,
            timeout=300 if name == 'boot-status' else 1200)
    if result.returncode and not allow_failure:
        raise RuntimeError(f"{name} failed")
    print(name + (": passed." if result.returncode == 0 else ": did not succeed; diagnostics kept private."), flush=True)
    return result.returncode


def fetch():
    validate_ref()
    LOGS.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if api(f"/repos/{SOURCE_REPO}").get('private') is not True:
        raise RuntimeError('Source repository must remain private')
    commit = api(f"/repos/{SOURCE_REPO}/commits/{REF}")
    if commit["sha"] != REF:
        raise RuntimeError("Source identity mismatch")
    blob = api(f"/repos/{SOURCE_REPO}/zipball/{REF}", binary=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        roots = {item.filename.split("/")[0] for item in archive.infolist()}
        if len(roots) != 1:
            raise RuntimeError("Unexpected source archive")
        for item in archive.infolist():
            parts = Path(item.filename).parts[1:]
            if not parts:
                continue
            destination = SOURCE.joinpath(*parts).resolve()
            if not destination.is_relative_to(SOURCE.resolve()):
                raise RuntimeError("Unsafe source archive path")
            if item.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(item))
    (OUTPUT / "source-verification.json").write_text(json.dumps(dict(repository=SOURCE_REPO, source_ref=REF, run_id=RUN, run_attempt=ATTEMPT), indent=2))
    print("Immutable private source verified. Detailed source output is withheld.")


def prepare():
    validate_ref()
    candidates = []
    for app in Path('/Applications').glob('Xcode_26*.app'):
        match = re.fullmatch(r'Xcode_([0-9]+(?:\.[0-9]+)*)\.app', app.name)
        if match:
            candidates.append((tuple(int(value) for value in match.group(1).split('.')), app))
    if not candidates:
        raise RuntimeError('A stable Xcode26 SDK is required for the native music interface')
    preferred = max(candidates)[1] / 'Contents/Developer'
    command("select-xcode", ["sudo", "xcode-select", "-s", str(preferred)])
    # Tool versions do not contain private-source information.
    print(subprocess.check_output(["xcodebuild", "-version"], text=True).strip())
    print(subprocess.check_output(["swift", "--version"], text=True).strip())
    fixture = SOURCE / "VerseLensTests/Fixtures/demo-lessons.json"
    generated_paths = [fixture if fixture.is_file() else SOURCE / "VerseLens/Resources/demo-lessons.json", SOURCE / "VerseLens.xcodeproj/project.pbxproj", SOURCE / "VerseLens.xcodeproj/xcshareddata/xcschemes/VerseLens.xcscheme"]
    before = [hashlib.sha256(path.read_bytes()).digest() for path in generated_paths]
    command("generate-demo", ["python3", "scripts/build_demo.py"])
    command("generate-project", ["python3", "scripts/generate_project.py"])
    if before != [hashlib.sha256(path.read_bytes()).digest() for path in generated_paths]:
        raise RuntimeError("Generated source is not reproducible")
    command("plist", ["plutil", "-lint", "VerseLens/Info.plist", "VerseLens/PrivacyInfo.xcprivacy", "VerseLens.xcodeproj/project.pbxproj"])
    command("audit-tests", ["python3", "scripts/test_ipa_audit.py"])
    print("Project and packaging validation passed.")


def core():
    command("core-tests", ["swift", "test"])
    if (SOURCE / 'scripts/probe_catalog.py').is_file():
        command('catalog-live-probe', ['python3', 'scripts/probe_catalog.py', '--output', str(OUTPUT / 'catalog-live-probe.json')])
    if (SOURCE / 'scripts/probe_lrclib.py').is_file():
        command('lrclib-live-probe', ['python3', 'scripts/probe_lrclib.py', '--output', str(OUTPUT / 'lrclib-live-probe.json')])
    if (SOURCE / 'scripts/probe_home.py').is_file():
        command('home-live-probe', ['python3', 'scripts/probe_home.py', '--output', str(OUTPUT / 'home-live-probe.json')])
    print("Foundation core tests passed. Detailed results remain private.")


def compile_app():
    command('simulator-build', ['xcodebuild', 'build-for-testing', '-project', 'VerseLens.xcodeproj', '-scheme', 'VerseLens',
        '-configuration', 'Debug', '-destination', 'generic/platform=iOS Simulator', '-derivedDataPath', str(ROOT / 'DerivedData'), 'CODE_SIGNING_ALLOWED=NO'])
    (OUTPUT / 'simulator-build.json').write_text(json.dumps(dict(source_ref=REF, result='success')))
    print('Simulator app and test bundles compiled successfully.', flush=True)


def export_results():
    result = ROOT / "TestResults.xcresult"
    if result.is_dir():
        command("export-screenshots", ["xcrun", "xcresulttool", "export", "attachments", "--path", str(result), "--output-path", str(ROOT / "screenshots")], allow_failure=True)
        with (OUTPUT / "test-summary.json").open("wb") as output:
            subprocess.run(["xcrun", "xcresulttool", "get", "test-results", "summary", "--path", str(result)], stdout=output, stderr=subprocess.DEVNULL, check=False)


def simulator():
    inventory = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"]))
    choices = [(runtime, device) for runtime, devices in inventory["devices"].items() if ".iOS-26-" in runtime for device in devices if device.get("isAvailable") and "iPhone" in device["name"]]
    choices.sort(key=lambda pair: (0 if "16e" in pair[1]["name"] else 1 if "17e" in pair[1]["name"] else 2 if pair[1]["name"] == 'iPhone 17' else 3, pair[0], pair[1]["name"]))
    if not choices:
        raise RuntimeError("No installed iOS26 iPhone simulator")
    runtime, device = choices[0]
    (OUTPUT / "simulator.json").write_text(json.dumps(dict(runtime=runtime, device=device), indent=2))
    command("boot-simulator", ["xcrun", "simctl", "boot", device["udid"]], allow_failure=True)
    command("boot-status", ["xcrun", "simctl", "bootstatus", device["udid"], "-b"])
    result = command("xcode-tests", ["xcodebuild", "test-without-building", "-project", "VerseLens.xcodeproj", "-scheme", "VerseLens", "-configuration", "Debug",
        "-destination", f"platform=iOS Simulator,id={device['udid']}", "-derivedDataPath", str(ROOT / "DerivedData"),
        "-resultBundlePath", str(ROOT / "TestResults.xcresult"), "-parallel-testing-enabled", "NO", "CODE_SIGNING_ALLOWED=NO"], allow_failure=True)
    export_results()
    if result:
        raise RuntimeError("Simulator build or tests failed")
    print("Simulator build, unit tests and UI tests passed.")


def archive():
    key = os.environ.get('YOUTUBE_API_KEY', '')
    if key:
        if re.fullmatch(r'[A-Za-z0-9_-]+', key) is None:
            raise RuntimeError('Invalid optional video-search key')
        (SOURCE / 'Config/Secrets.xcconfig').write_text('YOUTUBE_API_KEY = ' + key + '\n')
    archive_path = ROOT / "VerseLens.xcarchive"
    ipa = OUTPUT / "VerseLens-unsigned.ipa"
    command("archive", ["xcodebuild", "archive", "-project", "VerseLens.xcodeproj", "-scheme", "VerseLens", "-configuration", "Release",
        "-destination", "generic/platform=iOS", "-archivePath", str(archive_path), "-derivedDataPath", str(ROOT / "ArchiveDerivedData"),
        "CODE_SIGNING_ALLOWED=NO", "CODE_SIGNING_REQUIRED=NO", f"CURRENT_PROJECT_VERSION={NUMBER}"])
    command("package", ["python3", "scripts/package_ipa.py", str(archive_path / "Products/Applications/VerseLens.app"), str(ipa)])
    command("ipa-audit", ["python3", "scripts/audit_ipa.py", str(ipa), "--output", str(OUTPUT / "ipa-audit.json")])
    digest = hashlib.sha256(ipa.read_bytes()).hexdigest()
    (OUTPUT / "SHA256SUMS").write_text(digest + "  VerseLens-unsigned.ipa\n")
    print("Unsigned iPhone archive and IPA integrity audit passed.")


def publish():
    validate_ref()
    if not SOURCE.exists():
        print("No private checkout; nothing to publish.")
        return
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if api(f"/repos/{SOURCE_REPO}").get('private') is not True:
        raise RuntimeError('Artifact destination must remain private')
    success = os.environ.get("BUILD_OUTCOME") == "success" and (OUTPUT / "ipa-audit.json").is_file()
    export_results()
    receipt = dict(source_ref=REF, outcome="success" if success else "failure", run_id=RUN, run_number=NUMBER, run_attempt=ATTEMPT,
        controller=f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{RUN}")
    (OUTPUT / "build-verification.json").write_text(json.dumps(receipt, indent=2))
    diagnostics = OUTPUT / "VerseLens-diagnostics.zip"
    with zipfile.ZipFile(diagnostics, "w", zipfile.ZIP_DEFLATED) as bundle:
        for directory, label in [(LOGS, "logs"), (ROOT / "TestResults.xcresult", "TestResults.xcresult"), (ROOT / "screenshots", "screenshots")]:
            if directory.exists():
                for path in directory.rglob("*"):
                    if path.is_file():
                        bundle.write(path, label + "/" + path.relative_to(directory).as_posix())
        for path in OUTPUT.glob("*.json"):
            bundle.write(path, path.name)
    tag = f"private-build-{NUMBER}-a{ATTEMPT}-{REF[:12]}"
    body = f"Private VerseLens build. Source `{REF}`. Outcome: {'success' if success else 'failure; diagnostics only'}. Unsigned IPA requires signing before installation."
    try:
        release = api(f"/repos/{SOURCE_REPO}/releases/tags/{tag}")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        release = api(f"/repos/{SOURCE_REPO}/releases", "POST", dict(tag_name=tag, target_commitish=REF,
            name=f"VerseLens v1 build {NUMBER}" + ("" if success else " (diagnostics)"), body=body, prerelease=True))
    existing = {asset["name"]: asset for asset in api(f"/repos/{SOURCE_REPO}/releases/{release['id']}/assets")}
    paths = [diagnostics, OUTPUT / "build-verification.json", OUTPUT / "source-verification.json"]
    if success:
        paths += [OUTPUT / "VerseLens-unsigned.ipa", OUTPUT / "ipa-audit.json", OUTPUT / "SHA256SUMS"]
    for path in paths:
        if not path.is_file():
            continue
        if path.name in existing:
            api(f"/repos/{SOURCE_REPO}/releases/assets/{existing[path.name]['id']}", "DELETE")
        url = release["upload_url"].split("{")[0] + "?name=" + urllib.parse.quote(path.name)
        asset = api(url, "POST", path.read_bytes(), content_type="application/octet-stream")
        if path.name == "VerseLens-unsigned.ipa":
            redownloaded = api(f"/repos/{SOURCE_REPO}/releases/assets/{asset['id']}", binary=True, accept="application/octet-stream")
            expected, actual = hashlib.sha256(path.read_bytes()).hexdigest(), hashlib.sha256(redownloaded).hexdigest()
            if expected != actual:
                raise RuntimeError("Private asset redownload digest mismatch")
            verification = json.dumps(dict(source_ref=REF, sha256=actual, privateAssetDigestVerified=True, assetID=asset['id']), indent=2).encode()
            url = release['upload_url'].split('{')[0] + '?name=private-download-verification.json'
            if 'private-download-verification.json' in existing:
                api(f"/repos/{SOURCE_REPO}/releases/assets/{existing['private-download-verification.json']['id']}", "DELETE")
            api(url, "POST", verification, content_type="application/octet-stream")
    print("Private Release assets uploaded. " + ("Build succeeded." if success else "Build failed; private diagnostics uploaded."))
    print("Private result: " + release["html_url"])
    api(f"/repos/{SOURCE_REPO}/statuses/{REF}", "POST", dict(state='success' if success else 'failure',
        context='VerseLens public builder', description='iOS tests, archive and private asset verification passed' if success else 'Build failed; private diagnostics available',
        target_url=receipt['controller']))


def cleanup():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    print("Private checkout, logs, reports, archive and IPA removed from runner.")


if __name__ == "__main__":
    stage = sys.argv[1]
    try:
        {"fetch": fetch, "prepare": prepare, "core": core, "compile": compile_app, "simulator": simulator, "archive": archive, "publish": publish, "cleanup": cleanup}[stage]()
    except Exception:
        LOGS.mkdir(parents=True, exist_ok=True)
        (LOGS / f"controller-{stage}.log").write_text(traceback.format_exc())
        print(f"{stage} failed. Detailed diagnostics are withheld from public logs.")
        sys.exit(1)
