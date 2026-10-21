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
- Deployed 2026-10-20 to us-east-2 (stack `voice-rag-agent`): https://djsuuhec353rb2swjznsdofvlu0ejmpm.lambda-url.us-east-2.on.aws/ . BM25 retriever, DynamoDB state, SSM secrets, spend pause $5. ElevenLabs agent now points at this URL; the cloudflared tunnel is retired.
- Measured on Lambda: cold page load 6.2 s, warm /health 0.3 s; first token 980 ms (ES) and 487 ms (EN) vs 966 ms via tunnel; ~$0.0006 per turn.
- Region: an SCP (`p-3rzlv6oc`) limits this Free plan account to us-east-2 for regional services. Everything the stack needs works there.

## Next
1. Owner's real phone call after the cold-start fixes (not confirmed yet).
2. Owner reviews 30 judge verdicts in `eval/review/judge_spotcheck_v1.md`, which gives the judge error rate.
3. Biggest fix from FAILURES.md: inline `docs_src` code into chunks (677 of 1607 have placeholders), rebuild Titan vectors, rerun answer eval.
4. Showcase items left: latency p50/p95 from ~20 calls, public replay mode, demo video, Dockerfile, CV line.

## Waiting on the owner
- docs/LEARN.md steps 2 and 3 in us-east-2 (Titan probe, S3 Vectors bucket).
- Set a $50 spend limit in the Anthropic Console.

## Facts to remember
- 2026-10-20 showcase build: gold sample for owner review in `eval/review/gold_sample_v1.md` (pending). Ablation on cached Claude queries (`eval/ablation.py`): Titan V2 only recall@1 0.64, recall@5 0.96, MRR 0.78; beats local hybrid on recall@1 +0.20 [0.02, 0.38] and MRR +0.13 [0.013, 0.239]. Deployed `RETRIEVER=aws-dense`, bucket `fastapi-docs-vectors-rr6022`, index `docs-titan-v2-256`, retrieval 127 to 160 ms in Lambda (n=8). CI green (GitHub Actions). README now on frozen gold. Showcase plan: CV workspace `research_notes/Voice RAG agent 2026-10-20/SHOWCASE.md`.
- Cold starts were the "waits for the whole answer" problem: ElevenLabs gives up on the Custom LLM after ~4 s and retries (`agents_llm_service_failed_attempts_latency` in conversation turn metrics), and each Lambda instance serves one request, so the answer stream and trace polls need two. Fixes (2026-10-20): bytecode shipped in the bundle, 2048 MB, page warms 3 instances on load and on Start. Cold init is now ~4 s (3 s imports, 1 s startup). Not yet confirmed on the owner's phone. Warm calls measured by ElevenLabs: first audio 2.1 to 2.9 s after the user stops talking, LLM first byte 0.7 to 1.8 s, no failed attempts.
- index.html is served `Cache-Control: no-store`; a phone that kept an old copy polled `/trace` without session_id (422) and drew nothing.
- Agent voice is `eleven_v4_turbo` (90+ languages, ~100 ms) since 2026-10-20; Flash v2 was English only, so Spanish had an English accent. Eleven Realtime v1 Mini was rejected: it is a complete agent with its own LLM, so Claude, search_docs and the trace panel would drop out.
- ElevenLabs sends interrupted agent turns cut short, and internal search_docs calls never appear in the history. The prompt tells Claude not to comment on either.
- Spend is counted in two places: `costs/spend.jsonl` (local runs, evals) and the DynamoDB item `spend/total` (deployed demo, pauses at $5). Add both when checking the $40 pause.
- The agent must allow `platform_settings.overrides.custom_llm_extra_body`, or ElevenLabs ends every call at once with error 1008. With it on, `session_id` arrives and `/trace` requires it (no cross-visitor events).
- Haiku 5.5 runs with thinking disabled: the spoken filler starts at ~580 ms (adaptive thinking gave a silent tool call).
- ElevenLabs JS client pinned to 1.26.0 (has `customLlmExtraBody`, released 2026-09-29).
- Spend so far: see `uv run python -c "from voice_rag_agent.costs import Ledger; from voice_rag_agent.config import get_settings as g; s=g(); print(Ledger(s.spend_ledger, s.spend_pause_usd).total())"`.
- 2026-10-20 gold frozen (`eval-freeze-v1`, owner accepted 20 of 20 sampled rows). Answer eval on aws-dense, Opus 5.5 blind judge: Haiku 61/68 pass (0.90 [0.82, 0.96]), Sonnet 65/68 (0.96 [0.90, 1.00]), gap +0.06 [-0.015, 0.13] not significant; correct 0.98 both; Haiku $0.00057/turn, Sonnet $0.0198. Full run cost $3.25; ledger $3.70. Sonnet with between_tools thinking called record_sources before speaking and then said "."; fixed in 8d89f0a. Misses and causes in FAILURES.md.
