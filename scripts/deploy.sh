#!/bin/bash
# Package, push secrets, and deploy the stack. Prints the Function URL at the end.
#   scripts/deploy.sh            # BM25 retriever
#   RETRIEVER=aws S3VECTORS_BUCKET=fastapi-docs-vectors-xxxx scripts/deploy.sh
#   RETRIEVER=aws-dense S3VECTORS_BUCKET=... S3VECTORS_INDEX=docs-titan-v2-256-code \
#     INDEX_DIR=data/index_code scripts/deploy.sh   # chunks with code examples inlined
set -euo pipefail
cd "$(dirname "$0")/.."

# This account only allows regional services in us-east-2. The aws login session also
# needs a region to refresh its credentials.
export AWS_REGION=us-east-2 AWS_DEFAULT_REGION=us-east-2

# SAM does not read "aws login" sessions yet. Export the session's short-lived keys
# into this shell only; they expire with the session and are never written to disk.
eval "$(aws configure export-credentials --format env)"

# SAM rejects empty override values, so pass the bucket only when there is one.
overrides=("Retriever=${RETRIEVER:-bm25}")
[[ -n "${S3VECTORS_BUCKET:-}" ]] && overrides+=("VectorBucket=${S3VECTORS_BUCKET}")
[[ -n "${S3VECTORS_INDEX:-}" ]] && overrides+=("VectorIndex=${S3VECTORS_INDEX}")

scripts/package_lambda.sh
uv run --quiet scripts/push_secrets.py
sam deploy \
  --template-file infra/template.yaml \
  --stack-name voice-rag-agent \
  --region us-east-2 \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset --no-fail-on-empty-changeset \
  --parameter-overrides "${overrides[@]}"

aws cloudformation describe-stacks --stack-name voice-rag-agent --region us-east-2 \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionUrl'].OutputValue" --output text
