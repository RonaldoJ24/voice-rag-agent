# Failures and what they taught

Every miss from the frozen gold set (`eval-freeze-v1`, 68 rows), with the cause and the fix. Numbers come from `eval/results/answer_eval_summary.json` and `eval/results/ablation_claude-haiku-5-5.json`. Answers are judged by Claude Opus 5.5, blind to the model, against the reference answer and the sections that were actually retrieved.

## Summary

First run, before code inlining:

| | Haiku 5.5 (deployed) | Sonnet 5.5 |
|---|---|---|
| Judge pass, all 68 rows | 61 of 68, 0.90 [0.82, 0.96] | 65 of 68, 0.96 [0.90, 1.00] |
| Correct on answerable rows | 0.98 [0.94, 1.00] | 0.98 [0.94, 1.00] |
| Grounded in retrieved text | 0.92 [0.84, 0.98] | 0.96 [0.90, 1.00] |
| Unanswerable rows passed | 8 of 10 | 10 of 10 |
| Claude cost per turn | $0.00057 | $0.0198 |
| First token (the spoken filler), p50 | 584 ms | 935 ms |

Sonnet minus Haiku on judge pass: +0.06 [−0.015, 0.13]. The interval crosses zero, so 68 rows can't tell them apart. Haiku stays deployed. It costs 35 times less, and callers hear it sooner.

## 1. Code examples never reach the model (biggest cause)

**What failed.** 4 of Haiku's 7 failures and 2 of Sonnet's 3 are "correct but not grounded". In each one, the answer adds a true FastAPI detail that the retrieved text doesn't contain:

- en-05 (Haiku): raise `HTTPException` with status 404. Here retrieval also played a part. Haiku's hits had the Handling Errors intro but not `#use-httpexception`, the section that shows the pattern. Sonnet's hits included it, and Sonnet passed.
- en-14: the lifespan function is async, and the code before `yield` runs at startup.
- en-16: `root_path` can also be passed to the app.
- en-02: an invalid token is rejected before the route runs.

**Cause.** `scripts/build_chunks.py` swaps every code include for a placeholder such as `[code example: docs_src/events/tutorial003_py310.py]`. 677 of 1607 chunks (42%) lose their code this way. The prose around it often says "like this" and stops. So the model fills the gap from what it already knows. The facts are right, but nothing retrieved backs them.

**Fix (deployed 2026-10-21).** `scripts/build_chunks.py --code resolve` now inlines the `docs_src` files from the same FastAPI commit. It honors the `ln[a:b]` line ranges, and its merge decisions come from the placeholder layout, so every section id in the frozen gold set still exists. The vectors live in a second S3 Vectors index, `docs-titan-v2-256-code`, which the demo now uses. The old index is kept for rollback.

**Result.** Each condition was run twice and each question averaged over its two runs (`eval/compare_runs.py`, `eval/results/compare_code_vs_base.json`):

| | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| Judge pass, without code / with code | 0.90 / 0.95 | 0.95 / 0.93 |
| Paired difference, 68 questions | +0.05 [0.00, 0.11] | −0.02 [−0.08, 0.03] |
| Predicted rows passing in both code runs | en-05, en-14, en-16 (3 of 4) | en-14 (1 of 2) |
| Rows that flip between two runs of the same setup | 6 without code, 3 with code | 1 without code, 2 with code |
| Claude cost per turn | $0.000565 to $0.000597 (+6%) | $0.0199 to $0.0209 (+5%) |

- The cause was right. Every predicted row except en-02 now passes in both runs, and the judge points at the retrieved code. en-02 still fails because the right page never comes back (see 2).
- For Haiku the overall gain is at the edge of significance, because a rerun alone flips 3 to 6 rows.
- Sonnet got no better overall. On es-01 both code runs retrieved a different set of upload sections, without the prose that explains why UploadFile beats bytes. Inlined code moves the embeddings, which shifts the ranking for some queries.
- Retrieval with code inlined (Titan, same cached queries): recall@5 0.96 both, recall@1 0.64 to 0.58, difference −0.06 [−0.16, 0.04]. Local MiniLM dropped (recall@5 0.92 to 0.84), likely because it only reads the first 128 wordpieces.

## 2. Retrieval misses

**What failed.** On en-02 and es-12, no gold section reached the top 5 (Titan, `aws-dense`). Both are login questions.

- en-02 "How do I make a route need a login?" Haiku searched "route requires authentication login dependency" and got get-current-user and dependency pages. Sonnet searched "require authentication for a route, security dependency" and got OAuth2 scopes pages. The gold sections are on the OAuth2 first-steps page. Both models still gave a reasonable answer, but the judge failed them on the rejection claim (see 1).
- es-12 asks how to receive a username and password from a form. The gold section is the form-data page (`Form` plus `python-multipart`). Both models got OAuth2 and HTTP Basic pages instead, with nothing from the form-data page. Haiku answered with `OAuth2PasswordRequestForm` and missed the general answer. Sonnet said the form page wasn't retrieved and passed.

**Cause.** The OAuth2 tutorial uses words like "login", "form" and "password" more often than the general pages do, so it wins the ranking.

**Fix ideas.** Return 8 hits instead of 5 for questions about security, or let Claude search a second time when the hits all come from one page. Neither is built.

## 3. Unanswerable questions: invented extras

**What failed.** Haiku failed un-en-02 (Stripe) and un-es-05 (Locust load testing). Both times it correctly said the docs don't cover the topic. Then it added a FastAPI pointer that the hits didn't support:

- un-en-02: it said the callbacks page covers webhooks, which mixes up outgoing callbacks with the incoming webhooks Stripe sends.
- un-es-05: it pointed to a TestClient section that wasn't retrieved.

Sonnet passed all 10 unanswerable rows.

**Fix idea.** The prompt could say "after saying the docs don't cover it, only mention pages that were in the results". Not tested yet.

## 4. The deterministic abstention check disagrees with the judge

**What happened.** `abstained` is 8 of 10 for both models, but the judge passed un-en-04 (SendGrid email) and un-es-04 (Prometheus and Grafana) both times. Both models said the docs don't cover SendGrid or Prometheus. They then answered the part the docs do cover (background tasks, OpenTelemetry metrics) and set `answered_from_docs: true`.

**Cause.** The gold set calls these rows unanswerable, but part of each question is answerable. The code check only reads the flag, while the judge reads what was said.

**Decision.** Gold v1 is frozen, so the rows stay as they are. A v2 should mark these as partly answerable.

## 5. Sonnet with thinking skipped its answer (fixed)

**What failed.** In the first pilot run, all 5 of Sonnet's searched answers were only "Let me check the docs." The judge scored them 0.

**Cause.** With thinking on between tool calls, Sonnet called `record_sources` right after the search with no text, then ended the next round with a single ".". The loop took that as the end of the turn.

**Fix.** When sources are recorded before any answer text, the tool result now says the caller hasn't heard the answer yet (`src/voice_rag_agent/agent.py`, test in `tests/test_openai_compat.py`). This adds one silent thinking round before Sonnet speaks. The time from the filler to the first answer word was not measured, so it isn't in the table above.

**Second case.** On es-12 Sonnet searched twice, then recorded sources in round 3, the last one allowed, so it never spoke. The loop now adds one more round with `tool_choice: none` when the rounds run out. This was checked on the real API with thinking on. The first code run predates this fix, so its es-12 failure is this bug and not the code.

**Still open.** Once in two runs (un-es-03, Kafka), Sonnet recorded its sources first and then only offered to look up something related. It never said that the docs don't cover Kafka.

## 6. Code-like text in spoken answers

**What happened.** 3 of 68 answers per model failed `no_urls_or_code`, but the judge passed them all. They are en-04 and es-03 ("http://localhost:3000") and en-11 ("/users/{user id}"). Speech synthesis reads these out character by character.

**Fix idea.** Have `speakable()` rewrite `http://localhost:3000` as "localhost port 3000" and drop the braces. Not built.

An earlier version of this check matched the English word "import". It was narrowed to whole code lines before the full run.

## Not measured yet

- **Judge error.** 30 random judgments are in `eval/review/judge_spotcheck_v1.md` for human review. Until that review is done, the judge's own error rate is unknown.
- p50 and p95 voice latency over many calls, and Sonnet's extra silent round.
- Answer quality with the local retrievers. Only `aws-dense` was judged.
