"""Download the FastAPI docs at the current master commit into data/raw/.

The tarball is untrusted data: we only read and write bytes, never execute
anything from it, and we refuse links and paths that escape the target dir.
"""

import argparse
import datetime as dt
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "corpus_manifest.json"
KEEP = ("docs/en/docs/", "docs/es/docs/", "docs_src/")
KEEP_FILES = ("LICENSE",)


def resolve_sha() -> str:
    """Ask GitHub for the current master commit."""
    out = subprocess.run(
        ["gh", "api", "repos/fastapi/fastapi/commits/master", "--jq", ".sha"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def download(sha: str, dest: Path) -> None:
    """Stream the tarball for sha to dest."""
    url = f"https://codeload.github.com/fastapi/fastapi/tar.gz/{sha}"
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for part in r.iter_bytes():
                f.write(part)


def extract(tar_path: Path, out: Path) -> None:
    """Extract only the wanted regular files, dropping the top-level folder."""
    out_resolved = out.resolve()
    with tarfile.open(tar_path) as tar:
        for member in tar:
            if not member.isreg():  # skip dirs, symlinks, devices
                continue
            _, _, rel = member.name.partition("/")
            if not (rel.startswith(KEEP) or rel in KEEP_FILES):
                continue
            target = (out / rel).resolve()
            if not target.is_relative_to(out_resolved):
                raise ValueError(f"unsafe path in tarball: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(member)
            assert src is not None
            target.write_bytes(src.read())


def count(pattern: str) -> int:
    return sum(1 for p in RAW.glob(pattern) if p.is_file())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--force", action="store_true", help="re-download even if up to date"
    )
    args = ap.parse_args()

    sha = resolve_sha()
    up_to_date = (
        MANIFEST.exists()
        and RAW.exists()
        and json.loads(MANIFEST.read_text())["sha"] == sha
    )
    if up_to_date and not args.force:
        print(f"already extracted at {sha}; use --force to redo")
        return

    if RAW.exists():
        shutil.rmtree(RAW)
    RAW.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "fastapi.tar.gz"
        print(f"downloading {sha} ...")
        download(sha, tar_path)
        extract(tar_path, RAW)

    manifest = {
        "repo": "fastapi/fastapi",
        "sha": sha,
        "fetched": dt.date.today().isoformat(),
        "license": "MIT",
        "counts": {
            "docs_en_md": count("docs/en/docs/**/*.md"),
            "docs_es_md": count("docs/es/docs/**/*.md"),
            "docs_src_files": count("docs_src/**/*"),
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
