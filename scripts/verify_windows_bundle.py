"""Native Windows smoke check of the exact classroom ZIP, without installed Python for launch."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Run this verification on Windows")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {"status": "running", "checks": [], "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest()}
    child = None
    folder = None
    try:
        folder = tempfile.mkdtemp(prefix="수강생 자료 ")
        with zipfile.ZipFile(args.archive) as archive:
            archive.extractall(folder)
        root = Path(folder) / "DyninWorkshop"
        references = {'scripts/launch_offline.py': 'scripts/launch_offline.py',
                      'scripts/serve.py': 'scripts/serve.py',
                      'scripts/offline_launcher/START_WINDOWS.cmd': 'START_WINDOWS.cmd'}
        # Git blobs avoid Windows checkout newline conversion. Unit-tested source
        # and the exact delivered launch scripts must come from the same commit.
        source_root = Path(__file__).resolve().parents[1]
        for source, packaged in references.items():
            original = subprocess.check_output(['git', '-C', str(source_root), 'show', 'HEAD:' + source])
            assert (root / packaged).read_bytes() == original, 'Release/check-out mismatch: ' + source
        result['checks'].append('Packaged launcher/server/CMD match the unit-tested commit Git blobs')
        executable = root / "runtime/python/python.exe"
        version = subprocess.run([str(executable), "--version"], capture_output=True, text=True, check=True)
        result["python"] = version.stdout.strip()
        environment = os.environ.copy()
        # Deliberately remove any installed Python from the launch PATH.
        environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        command = ['cmd.exe', '/d', '/c', str(root / 'START_WINDOWS.cmd'), '--no-browser', '--duration-seconds', '12']
        child = subprocess.Popen(command, cwd=folder, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        base = "http://127.0.0.1:8922/"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(80):
            if child.poll() is not None:
                raise RuntimeError("Launcher exited before readiness: " + child.stdout.read().decode(errors="replace"))
            try:
                with opener.open(base + "__workshop_health", timeout=.5) as response:
                    health = json.load(response)
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError("Bundled launcher did not become ready")
        result["health"] = health
        result["checks"].append("CMD launches bundled Python with no installed Python on PATH, from a Korean/spaced path")
        manifest = json.loads((root / 'app/build-manifest.json').read_text(encoding='utf-8'))
        for suffix, expected_type in [(".mjs", "javascript"), (".wasm", "application/wasm"), (".pdf", "application/pdf")]:
            entry = next(x for x in manifest['files'] if x['path'].endswith(suffix) and x['path'].isascii())
            with opener.open(base + entry['path'], timeout=3) as response:
                assert expected_type in response.headers['Content-Type'], response.headers
                assert hashlib.sha256(response.read()).hexdigest() == entry['sha256']
            result['checks'].append(suffix + ' MIME and byte identity')
        video = next(x for x in manifest['files'] if x['path'].endswith(('.webm', '.mp4')) and x['path'].isascii())
        with opener.open(urllib.request.Request(base + video['path'], headers={'Range': 'bytes=30-999'}), timeout=3) as response:
            assert response.status == 206
            assert response.read() == (root / 'app' / video['path']).read_bytes()[30:1000]
        result['checks'].append('Native Windows video Range delivery')
        child.wait(timeout=20)
        result['launcher_output'] = child.stdout.read().decode(errors='replace')
        assert child.returncode == 0, result['launcher_output']
        result['checks'].append('Finite invocation shuts down its server cleanly')
        result['status'] = 'passed'
    except Exception as error:
        result.update(status='failed', error=repr(error))
        raise
    finally:
        if child is not None and child.poll() is None:
            # Exact owned process tree only; never terminate a process found by a shared port/name.
            subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True)
            child.wait(timeout=10)
        if folder is not None:
            try:
                shutil.rmtree(folder)
            except OSError as error:
                result['cleanup_error'] = repr(error)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # The runner console may be CP1252 even though the saved receipt is UTF-8.
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
