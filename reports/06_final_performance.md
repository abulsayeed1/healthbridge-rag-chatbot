# 06 — Final Performance

**Owner:** Manish Karki (Evaluations & Reranking) · **Status: DRAFT — dev-split results; final numbers pending the single frozen test run (Sunday, tag `v-final`).**

## 1. Methodology

- **Golden set:** 49 items (19 single-hop, 7 multi-hop, 5 comparative, 5 temporal, 9 unanswerable, 4 ambiguous/adversarial), authored 2026-10-10 from 14 live UCSF Health documents (10 HTML pages + 4 policy PDFs; see `reports/golden_set_sources.md` for per-item source links, locations and verbatim quotes). Human verification pass in progress; results below are **draft** until complete.
- **Split:** 60/40 stratified by category, `random_state=633`; partitions frozen in `eval/golden_set.dev.jsonl` (28) / `eval/golden_set.test.jsonl` (21). All tuning on dev only.
- **Relevance:** chunk from a gold `source_url` **and** containing the `evidence_quote` (token-set ratio ≥ 0.85) — keyed to URL+quote, not chunk IDs, so labels survive re-chunking.
- **Systems (ablation ladder, one factor changed per row):** B0 BM25-only → B1 dense-only → B2 hybrid (BM25 + dense, RRF k=60) → B3 hybrid + cross-encoder rerank (pool 30 → top 5).
- **Metrics:** Recall@5, Recall@20 (reranker ceiling), MRR, nDCG@10 (answerable items); correct-refusal and over-refusal rates; all seeded 633.
- **Uncertainty:** paired bootstrap (10,000 resamples, 95% percentile CI) on every metric delta + exact McNemar on per-item pass/fail. Differences are called "not significant" whenever the CI crosses zero.
- **Dev stack:** corpus = 116 chunks from the 14 source docs · embedder `all-MiniLM-L6-v2` · reranker `cross-encoder/ms-marco-MiniLM-L-6-v2` · τ = 0.5.

## 2. Dev-split results (n=28; answerable items for IR metrics)

| System | Recall@5 | Recall@20 | MRR | nDCG@10 |
|---|---|---|---|---|
| B0 — BM25 only | 0.714 | 0.857 | 0.486 | 0.534 |
| B1 — dense only | 0.762 | 0.952 | 0.651 | 0.676 |
| B2 — hybrid RRF | 0.810 | 1.000 | 0.622 | 0.640 |
| **B3 — hybrid + rerank** | **0.905** | **1.000** | **0.823** | **0.829** |

Refusal behavior (B3, τ=0.5): correct-refusal 0.286 (unanswerable) · over-refusal 0.095 (answerable). B0–B2 have no calibrated evidence gate.

## 3. Significance (paired, dev)

- **Reranker effect (B3 − B2):** MRR **+0.201 [0.065, 0.352] — significant**; nDCG@10 **+0.189 [0.047, 0.339] — significant**; Recall@5 +0.095 [−0.143, 0.333] — not significant; McNemar exact p = 0.6875 (Recall@5 wins B3=4, B2=2).
- **Fusion effect (B2 − B1):** all deltas not significant (Recall@5 +0.048 [−0.143, 0.238]; MRR −0.029; nDCG −0.036).
- **Dense vs lexical (B1 − B0):** all deltas not significant (Recall@5 +0.048 [−0.190, 0.286]).

**Reading:** Recall@20 = 1.0 from B2 up means nothing relevant is lost before reranking — top-5 failures are ranking failures, which is exactly what B3 fixes (MRR/nDCG gains).

## 4. Test protocol (to be executed once)

1. Complete the golden-set human verification pass (claim table in `reports/golden_set_sources.md`).
2. Wire production `rerank/reranker.py` to the same scorer as the harness (done in `feat(rerank)` commit; confirm model loads).
3. Freeze config, tag `v-final`, run the test split **exactly once**, record commit hashes here.
4. Re-report §2–§3 tables on test; add B0-leakage subset re-report and ≥15 hand-labeled failures using the §5 taxonomy.

## 5. Known limitations

- Golden set is AI-drafted; all conclusions are provisional until the verification pass completes.
- Dev corpus (116 chunks, 14 docs) is a fraction of the ~300-page target crawl; absolute numbers will move.
- Dev reranker is a light MiniLM cross-encoder; final run uses `BAAI/bge-reranker-base`.
- n ≈ 20 test items → wide CIs by construction; reported honestly rather than over-claimed.
