# STATE

Where the build stands, so any session can resume. Update after every milestone.

## Done
- Repo, uv project, retriever interface (`src/voice_rag_agent/retrieval/base.py`).
- Proxy: OpenAI-compatible `/v1/chat/completions` streaming Claude Haiku 5.5, `search_docs` + `record_sources` tools, trace events, spend ledger (`costs/spend.jsonl`). Smoke-tested with a fake retriever.
- Demo page `web/index.html` (voice + live trace panel), ElevenLabs agent script `scripts/elevenlabs_agent.py`, hands-on guide `docs/LEARN.md`.

## In progress
- Corpus fetch, chunking and local hybrid retriever (`scripts/fetch_corpus.py`, `scripts/build_chunks.py`, `scripts/build_index.py`, `retrieval/local.py`).

## Next
1. Local server + cloudflared tunnel, create the ElevenLabs agent, first spoken turn with live trace.
2. Gold set v1 (60 questions + 8 small-talk turns), frozen with tag `eval-freeze-v1`.
3. Retrieval eval, then AWS: Titan + S3 Vectors probe (owner runs docs/LEARN.md steps 1 to 3), Lambda deploy with SAM.
4. Answer eval (Haiku vs Sonnet, Opus judge), voice eval, README results.

## Waiting on the owner
- `aws login --region us-east-1` and docs/LEARN.md steps 2 and 3.
- Set a $50 spend limit in the Anthropic Console.

## Facts to remember
- Haiku 5.5 runs with thinking disabled: the spoken filler starts at ~580 ms (adaptive thinking gave a silent tool call).
- ElevenLabs JS client pinned to 1.26.0 (has `customLlmExtraBody`, released 2026-09-29).
- Spend so far: see `uv run python -c "from voice_rag_agent.costs import Ledger; from voice_rag_agent.config import get_settings as g; s=g(); print(Ledger(s.spend_ledger, s.spend_pause_usd).total())"`.
