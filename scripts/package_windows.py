"""Build the optional Windows classroom ZIP from the reviewed static manifest."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import urllib.request
import zipfile

from build import ROOT, safe_file

RUNTIME = {
    "version": "3.14.10",
    "platform": "Windows x64",
    "url": "https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip",
    "sha256": "90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159",
    "release": "https://www.python.org/downloads/release/python-31410/",
}


def runtime_archive(path=None):
    if path is None:
        path = ROOT / "validation/offline_runtime/python-3.14.10-embed-amd64.zip"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with urllib.request.urlopen(RUNTIME["url"], timeout=45) as response:
                content = response.read(25 * 1024 * 1024 + 1)
            if len(content) > 25 * 1024 * 1024:
                raise ValueError("Unexpectedly large Python runtime archive")
            if hashlib.sha256(content).hexdigest() != RUNTIME["sha256"]:
                raise ValueError("Python runtime differs from official SHA256")
            path.write_bytes(content)
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != RUNTIME["sha256"]:
        raise ValueError("Python runtime differs from official SHA256")
    return path


def package_windows(runtime=None):
    archive = runtime_archive(runtime)
    manifest = json.loads((ROOT / "dist/build-manifest.json").read_text())
    destination = ROOT / "workshop-windows.zip"
    prefix = "DyninWorkshop/"
    launch = {
        "scripts/offline_launcher/START_WINDOWS.cmd": "START_WINDOWS.cmd",
        "scripts/offline_launcher/README.ko.txt": "읽어주세요.txt",
        "scripts/launch_offline.py": "scripts/launch_offline.py",
        "scripts/serve.py": "scripts/serve.py",
    }
    for source in launch:
        safe_file(ROOT / source)
    entries = []
    for entry in manifest["files"]:
        rel = PurePosixPath(entry["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unsafe static manifest member")
        source = ROOT / "dist" / str(rel)
        safe_file(source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Static build changed after manifest: " + str(rel))
        entries.append((source, prefix + "app/" + str(rel)))
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as output:
        for source, target in entries:
            output.write(source, target)
        output.write(ROOT / "dist/build-manifest.json", prefix + "app/build-manifest.json")
        for source, target in launch.items():
            output.write(ROOT / source, prefix + target)
        with zipfile.ZipFile(archive) as embedded:
            for member in embedded.infolist():
                rel = PurePosixPath(member.filename)
                if rel.is_absolute() or ".." in rel.parts or "\\" in member.filename:
                    raise ValueError("Unsafe runtime archive member")
                if member.is_dir():
                    continue
                output.writestr(prefix + "runtime/python/" + str(rel), embedded.read(member))
        output.writestr(prefix + "runtime/PROVENANCE.json", json.dumps(RUNTIME, indent=2) + "\n")
    with zipfile.ZipFile(destination) as result:
        bad = result.testzip()
        if bad:
            raise ValueError("Corrupt Windows ZIP member: " + bad)
        count = len(result.namelist())
    return {"file": destination.name, "bytes": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "files": count, "runtime": RUNTIME,
            "entrypoint": "DyninWorkshop/START_WINDOWS.cmd",
            "optional_backup": True, "requires_python_install": False}
