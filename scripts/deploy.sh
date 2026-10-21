#!/bin/bash
# Package, push secrets, and deploy the stack. Prints the Function URL at the end.
#   scripts/deploy.sh            # BM25 retriever
#   RETRIEVER=aws S3VECTORS_BUCKET=fastapi-docs-vectors-xxxx scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# SAM does not read "aws login" sessions yet. Export the session's short-lived keys
# into this shell only; they expire with the session and are never written to disk.
eval "$(aws configure export-credentials --format env)"

scripts/package_lambda.sh
uv run --quiet scripts/push_secrets.py
sam deploy \
  --template-file infra/template.yaml \
  --stack-name voice-rag-agent \
  --region us-east-1 \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset --no-fail-on-empty-changeset \
  --parameter-overrides "Retriever=${RETRIEVER:-bm25}" "VectorBucket=${S3VECTORS_BUCKET:-}"

aws cloudformation describe-stacks --stack-name voice-rag-agent --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionUrl'].OutputValue" --output text
