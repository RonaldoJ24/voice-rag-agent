#!/bin/bash
# Build the Lambda bundle in build/lambda: arm64 Linux wheels plus the code, the page and
# the text-only index (chunks and BM25). Dense vectors live in S3 Vectors, not here.
# manylinux_2_28 matches the python3.13 runtime (Amazon Linux 2023, glibc 2.34).
set -euo pipefail
cd "$(dirname "$0")/.."

out=build/lambda
rm -rf "$out"
mkdir -p "$out/data/index"

uv export --frozen --no-dev --no-default-groups --no-hashes --no-emit-project \
  --quiet -o build/requirements.txt
uv pip install --quiet --target "$out" -r build/requirements.txt \
  --python-platform aarch64-manylinux_2_28 --python-version 3.13 --only-binary :all:

cp -R src web "$out/"
cp data/index/chunks.jsonl data/index/bm25.json data/index/meta.json "$out/data/index/"
cp infra/run.sh "$out/run.sh"
# Ship bytecode. /var/task is read-only, so without it every cold start recompiles
# every module (anthropic alone is over a second). unchecked-hash keeps the .pyc valid
# even though zipping changes file times.
find "$out" -name __pycache__ -prune -exec rm -rf {} +
uv run --quiet python -m compileall -q -j 0 --invalidation-mode unchecked-hash "$out" || true

echo "Bundle: $(du -sh "$out" | cut -f1) unzipped (Lambda limit 250 MB with layers)"
