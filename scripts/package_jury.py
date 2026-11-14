"""Build the portable jury demo from an explicit allowlist; stdlib only."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/submission/PITWALL_Offline_Demo.zip"


def main():
    paths = set()
    for folder, pattern in [("demo_fallback", "*"), ("artifacts/demo", "*.json")]:
        for path in (ROOT / folder).rglob(pattern):
            if path.is_file() and (folder != "demo_fallback" or path.suffix in {".html", ".css", ".js"}):
                paths.add(path)
    for name in ["scripts/serve_demo.py", "src/pitwall/__init__.py",
                 "src/pitwall/engineer.py", "docs/JURY_PRESENTATION.md",
                 "artifacts/submission/PITWALL_Jury_Final.pptx"]:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        paths.add(path)
    contents = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(paths)}
    # An extracted package cannot download itself; preserve the working PPTX link.
    pitch = contents["demo_fallback/pitch.html"].decode("utf-8")
    pitch = pitch.replace('<a href="../artifacts/submission/PITWALL_Offline_Demo.zip" download>Offline demo ↓</a>', '')
    contents["demo_fallback/pitch.html"] = pitch.encode("utf-8")
    contents["START_DEMO.cmd"] = (
        '@echo off\r\ncd /d "%~dp0"\r\n'
        'echo Open http://127.0.0.1:8001/demo_fallback/ after the server starts.\r\n'
        'python scripts\\serve_demo.py --port 8001\r\npause\r\n'
    ).encode()
    contents["START_HERE.txt"] = (
        "PITWALL - Tyre Degradation Intelligence\n\n"
        "Extract the entire ZIP first. Requires Python 3.10 or later.\n"
        "Windows: double-click START_DEMO.cmd.\n"
        "macOS/Linux: python3 scripts/serve_demo.py --port 8001\n"
        "Open http://127.0.0.1:8001/demo_fallback/ and click Present to jury.\n"
        "Keep the terminal open; Ctrl+C stops the server. If port 8001 is in use,\n"
        "choose another --port and use that port in the browser.\n\n"
        "No pip/npm install, cloud or internet is required for viewing.\n"
        "Predictions are precomputed historical replay, not live inference.\n"
        "Engineer commentary uses deterministic facts by default.\n"
        "The optional local Ollama model is not included or required.\n"
        "Training caches and dependencies are excluded.\n"
        "The Offline demo download link belongs to the original host; this ZIP\n"
        "does not contain another copy of itself.\n\n"
        "Walkthrough: docs/JURY_PRESENTATION.md\n"
        "Deck: artifacts/submission/PITWALL_Jury_Final.pptx\n"
        "Browser slides: http://127.0.0.1:8001/demo_fallback/pitch.html\n"
    ).encode()
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(contents.items())}
    contents["MANIFEST.json"] = json.dumps(manifest, indent=2).encode()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(contents.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 12, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Package CRC check failed")
    print(f"Packaged {len(contents)} files: {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
