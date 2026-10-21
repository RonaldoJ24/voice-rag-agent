#!/bin/bash
# Lambda entry point. The Web Adapter starts this, waits for the readiness path, then
# forwards each request to uvicorn and streams the response back.
export PYTHONPATH="/var/task/src:/var/task:${PYTHONPATH}"
exec python3 -m uvicorn voice_rag_agent.app:app \
  --host 0.0.0.0 --port "${AWS_LWA_PORT:-8080}" --no-access-log
