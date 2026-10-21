# STATE

Where the build stands, so any session can resume. Update after every milestone.

## Done
- Repo, uv project, retriever interface (`src/voice_rag_agent/retrieval/base.py`).
- Proxy: OpenAI-compatible `/v1/chat/completions` streaming Claude Haiku 5.5, `search_docs` + `record_sources` tools, trace events, spend ledger (`costs/spend.jsonl`). Smoke-tested with a fake retriever.
- Demo page `web/index.html` (voice + live trace panel), ElevenLabs agent script `scripts/elevenlabs_agent.py`, hands-on guide `docs/LEARN.md`.

- Corpus at fastapi commit b2ce629: 122 pages per language, 801 EN + 806 ES chunks (`data/chunks.jsonl`). Local hybrid retriever (multilingual MiniLM + BM25, RRF, ~3 ms/query).
- ElevenLabs agent `agent_7901m5e1zkkef58sc7shr7gtnssk` (private, Custom LLM -> proxy `/v1`, Bearer secret, eleven_flash_v2, ES preset). Simulated conversation passed end to end, including `end_call`.
- AWS retriever code (Titan V2 + S3 Vectors + BM25) and `scripts/build_s3vectors.py`, untested until `aws login`.
- Gold set draft (68 rows) and retrieval evals on Claude-written queries: hybrid recall@5 0.94, BM25-only 0.92 (`eval/results/`).
- Lambda deploy ready, not yet run: `infra/template.yaml` (Web Adapter v30, streaming Function URL, DynamoDB state, SSM secrets), `scripts/deploy.sh`. Bundle 136 MB unzipped. `STATE_BACKEND=dynamodb`, `RETRIEVER=bm25` by default.
- Live panel polls `/trace?after=<cursor>`; `/api/session` returns the starting cursor and checks `X-Demo-Code`.

## In progress
- Deploy blocked (2026-10-20). Verification cleared for Bedrock (Titan V2 embed call works), but SCP `p-3rzlv6oc` from the management account 767866852456 still explicitly denies Lambda, DynamoDB, CloudFormation, SSM, Secrets Manager, S3 Vectors and EC2 on account 784514617897. The owner has to inspect or detach it in Organizations > Policies. Nothing was created.

## Next
1. Owner's first real voice call on http://localhost:8000 (server + cloudflared quick tunnel must be running; quick-tunnel URL changes on restart, then rerun `scripts/elevenlabs_agent.py --base-url <url>`).
2. Gold set v1 (60 questions + 8 small-talk turns), frozen with tag `eval-freeze-v1`.
3. After `aws login`: `scripts/deploy.sh`, curl `/health` from outside (403 means the Function URL permission is wrong), `scripts/smoke_proxy.py --base-url <url>`, compare first-token time with 966 ms via tunnel, point the ElevenLabs agent at the Function URL. Then Titan probe, `build_s3vectors.py`, eval with `--retriever aws`, redeploy with `RETRIEVER=aws`.
4. Answer eval (Haiku vs Sonnet, Opus judge), voice eval, README results.

## Waiting on the owner
- `aws login --region us-east-1` and docs/LEARN.md steps 2 and 3.
- Set a $50 spend limit in the Anthropic Console.

## Facts to remember
- Spend is counted in two places: `costs/spend.jsonl` (local runs, evals) and the DynamoDB item `spend/total` (deployed demo, pauses at $5). Add both when checking the $40 pause.
- `/trace` with no session filter returns every visitor's events. Once the first real call shows whether `session_id` arrives in `elevenlabs_extra_body`, filter server side and drop the "latest" fallback.
- Haiku 5.5 runs with thinking disabled: the spoken filler starts at ~580 ms (adaptive thinking gave a silent tool call).
- ElevenLabs JS client pinned to 1.26.0 (has `customLlmExtraBody`, released 2026-09-29).
- Spend so far: see `uv run python -c "from voice_rag_agent.costs import Ledger; from voice_rag_agent.config import get_settings as g; s=g(); print(Ledger(s.spend_ledger, s.spend_pause_usd).total())"`.
