# Interview Prep — Manish Karki (Data Scientist: Evaluations & Reranking)

HealthBridge — UCSF Health Patient Navigator (RAG Chatbot) · MSAI 633 Residency Project
Owner: reranking (Stage 8), evaluation harness, Report 06, golden set (shared with Ravalika)

---

## 1. Elevator paragraph (what I did)

As the Data Scientist owning Evaluations & Reranking for HealthBridge's UCSF Health patient-navigator RAG chatbot, I designed Stage 8 — a cross-encoder reranking layer that rescores the top-30 hybrid-retrieval candidates (BM25 + dense embeddings fused via reciprocal rank fusion) and keeps the best 5, with sigmoid scores feeding the evidence gate that decides when the bot should refuse rather than answer. I drafted the project's entire 49-question golden evaluation set from the live UCSF Health pages — balanced across six categories (19 single-hop, 7 multi-hop, 5 comparative, 5 temporal, 9 unanswerable, 4 ambiguous/adversarial) to match the §8.1 targets — made it fully conformant to the team's JSON schema, and committed it along with a verification protocol for the seven-member team. I then built and merged the evaluation harness that runs the B0–B3 ablation ladder, computes Recall@5/Recall@20, MRR, nDCG@10, and refusal rates per configuration, and quantifies each pipeline upgrade with paired bootstrap 95% confidence intervals (10,000 resamples) and exact McNemar tests — producing the dev-split results that statistically confirmed the reranking stage's impact and set the baseline for the frozen single test run.

## 2. Golden set — where the data came from

I authored all 49 questions from **14 primary documents** pulled live from ucsfhealth.org on October 10, 2026:

- **10 HTML pages** from the in-scope `/patients-visitors/**` section of the official sitemap (5,852 URLs, discovered via `sitemap.xml`):
  - `/patients-visitors/billing-insurance/help-paying-your-bill/`
  - `/patients-visitors/billing-insurance/health-insurance/`
  - `/patients-visitors/medical-records/`
  - `/patients-visitors/second-opinion/`
  - `/patients-visitors/billing-insurance/no-surprises-billing-act/`
  - `/patients-visitors/visitors/`, `/your-hospital-stay/`, `/support-services/`, `/appointments/`, `/billing-insurance/` (hub)
- **4 policy PDFs** from UCSF's own CDN (edge.sitecorecloud.io):
  - `patient_financial_assistance_policy_30407.pdf` (12 pages, policy 3.04.07)
  - `self_pay_discount_policy_30406.pdf` (5 pages, policy 3.04.06)
  - `debt-collection-030408.pdf` (5 pages, policy 3.04.08)
  - `financial_assistance_application.pdf` (6 pages)

Pages were fetched politely (1 req/sec, descriptive user-agent `MSAI633-RAGBot/0.1`, robots.txt respected), HTML parsed to text with BeautifulSoup, PDFs with pypdf. Every gold answer plus its ≤25-word verbatim evidence quote was lifted from that extracted text — not from memory. Those 14 documents became the **116-chunk retrieval corpus** for the dev evaluation, so questions and corpus share one provenance chain: every KPI traces back to a real fetched page. Two categories are deliberately "negative": 9 unanswerable questions (cafeteria menus, ER wait times, personal balances) required actually searching the site and confirming absence, with the search logged in a `searched_for` field.

Category breakdown (§8.1 targets): 19 single-hop · 7 multi-hop · 5 comparative · 5 temporal · 9 unanswerable · 4 ambiguous/adversarial = 49 (course minimum was 40; the over-quota is risk-R5 mitigation for the small test split).

## 3. Reranking — why a cross-encoder, and what I rejected

**Core argument:** Stage 7 bi-encoders embed the query and chunks *separately*, then compare vectors — O(1) per document at query time, but blind to token-level interactions. A **cross-encoder concatenates (query, chunk) into one transformer pass**, so it sees that "Medi-Cal" in the question matches "Medi-Cal managed care" in the chunk, or that policy code "3.04.07" appears verbatim — exactly this domain's failure mode (plan names, policy numbers, dollar figures). Cost is O(n) transformer passes, so it only runs on a small pool: **pool of 30 → top 5** — big enough that dev Recall@20 hit 1.0 (nothing relevant lost before reranking), small enough to bound latency.

| Alternative | Why not |
|---|---|
| Re-score with the same bi-encoder (cosine, bge-base) | Same signal as Stage 7, no new information; can't capture query–doc interactions. It's the retriever, not the reranker. |
| LLM reranking (gpt-4o-mini pointwise/listwise, RankGPT) | Highest ceiling, but per-query API cost × every config × every eval run, added latency, temperature non-determinism — breaks reproducibility of the frozen test run. |
| ColBERT / late interaction (PLAID) | Near cross-encoder quality with better scaling, but needs token-level index + custom serving — too much infra for a 3-day window. |
| monoT5 / duoT5 | Legitimate rivals; chose bge-reranker-base for sentence-transformers integration, strong BEIR/MsMarco numbers, local free inference. |
| RRF alone, no reranker | RRF fuses two ranked lists by rank position only — no notion of *why* a chunk is relevant; dev showed MRR 0.62 vs 0.82 after reranking. |

**Model detail:** production spec is **BAAI/bge-reranker-base** (~278M params, XLM-R base, relevance logit → sigmoid = evidence-gate score). The dev run used **cross-encoder/ms-marco-MiniLM-L-6-v2** (~22M params) to avoid a 1GB download and keep iteration fast — same architecture class; the harness quantifies what swapping the production model in should deliver. Trade-off to admit openly: iteration speed on dev, final config pinned before the single test run.

## 4. Eval design — why these metrics and tests

| Choice | Why | Rejected alternatives and why |
|---|---|---|
| Recall@5 / Recall@20 | "Did the answer survive into what the generator reads?" Recall@20 doubles as the **reranker's ceiling** — if it's 1.0, any top-5 failure is a *ranking* failure, not a retrieval miss; that separation powers the error taxonomy. | Precision@k misleading with ~1 relevant chunk per query; MAP redundant with so few relevant docs. |
| MRR | Position of the *first* relevant chunk — best proxy for answer quality with ranked chunks. | Graded metrics need multiple relevance labels; we have binary ones. |
| nDCG@10 | Position-sensitive AND handles multiple relevant chunks — essential for the 7 multi-hop questions. | ERR needs click-model assumptions we can't justify. |
| Exact McNemar | Paired **binary** pass/fail on the same items across two systems, tiny n (~20 test); exact binomial on discordant pairs is the textbook-correct test. | Paired t-test (normality, binary data, n=20); Wilcoxon (weaker for pass/fail); chi-square (unpaired — discards pairing, loses power). |
| Paired bootstrap CI (10,000 resamples) | Unknown sampling distribution of metric deltas at n≈20; bootstrap assumes nothing, preserves pairing; percentile CIs communicate honestly, including "crosses zero = not significant." | Analytic CIs (wrong distribution shape); Bayesian (overkill). |
| Stratified 60/40 split, seed 633, frozen | Guarantees every category in both dev and test — unstratified could leave zero unanswerables in a 20-item test set, making correct-refusal rate unmeasurable. Freezing prevents tuning leakage. | k-fold CV (more power, violates "test runs exactly once", over budget). |
| Relevance = gold URL + quote, fuzzy ≥0.85 token-set ratio | Survives re-chunking (chunk IDs change; URLs/quotes don't — risk R6); fuzzy absorbs whitespace/table artifacts. | Exact substring (breaks on re-chunk); embedding similarity (can't distinguish real quote from paraphrase). |
| B0–B3 ablation ladder | Each row changes exactly one factor → causal attribution of every pipeline upgrade. | Grid search (combinatorial, no attribution, needs more data than we have). |

## 5. KPI board (dev split, n=28, seed 633) — DRAFT until verification + test run

Corpus: 116 chunks from the 14 source docs · embedder: `all-MiniLM-L6-v2` · reranker: `ms-marco-MiniLM-L-6-v2` · τ=0.5 · seed 633

| System | Recall@5 | Recall@20 | MRR | nDCG@10 |
|---|---|---|---|---|
| B0 — BM25 only | 0.714 | 0.857 | 0.486 | 0.534 |
| B1 — dense only | 0.762 | 0.952 | 0.651 | 0.676 |
| B2 — hybrid RRF | 0.810 | 1.000 | 0.622 | 0.640 |
| **B3 — hybrid + rerank** | **0.905** | **1.000** | **0.823** | **0.829** |

Refusal (B3 only, τ=0.5): correct-refusal **28.6%** · over-refusal **9.5%**.

Statistical highlights (paired bootstrap, 95% CI, 10,000 resamples):
- **Reranker effect (B3−B2): MRR +0.201 [0.065, 0.352] ✅ significant · nDCG@10 +0.189 [0.047, 0.339] ✅ significant · Recall@5 +0.095 [−0.143, 0.333] ❌ not significant · McNemar exact p=0.6875**
- Hybrid vs dense (B2−B1) and dense vs BM25 (B1−B0): all CIs cross zero — not significant at this sample size

Caveats that must stay attached to these numbers:
1. Dev-split **draft** — golden set not yet human-verified.
2. Corpus is 116 chunks from 14 docs, not the full ~300-page crawl; absolute numbers will shift.
3. Dev used the light MiniLM cross-encoder; production `reranker.py` still bypasses its model — must adopt the same scorer before Sunday's single test run against the `v-final` tag.

## 6. Interview rapid-fire

- **"Is 20 test items statistically valid?"** — "No — underpowered by design constraints, and I say so explicitly. Mitigations: over-quota golden set (49 vs 40), bootstrap CIs instead of point estimates, McNemar for paired binary outcomes, and written 'not significant' when the CI crosses zero. I optimized for honesty, not false precision."
- **"Recall@5 wasn't significant — does the reranker even work?"** — "MRR (+0.20) and nDCG (+0.19) were significant with CIs excluding zero. Recall@5 had a ceiling effect: Recall@20 was already 1.0, so the reranker's job is reordering, which MRR measures directly. At ~21 dev items, Recall@5 only detects large swings."
- **"Golden set is AI-drafted — isn't it biased?"** — "Three controls: authored from live pages *before* the system existed (no teaching-to-the-test); mandatory human verification by a different member with `verifier`/`verified_at` fields; commit hash as timestamped proof of authorship-before-tuning. Unverified items are marked draft and excluded from final claims."
- **"How does the bot decide to refuse?"** — "Three layers: pre-LLM evidence gate on max cross-encoder sigmoid (τ tuned on dev only), LLM self-assessment in the system prompt, deterministic post-validator dropping uncited/unsupported sentences. I track correct-refusal AND over-refusal as a pair — refusing everything scores perfectly on one and fails the other."
- **"Why temperature 0 and pinned snapshot?"** — "Evals must be reproducible; a drifting generator would confound the ablation ladder."
- **"What was hardest / what broke?"** — Honest answers ready: production reranker bypasses its model (the harness quantifies what enabling it delivers); an old zip snapshot nearly overwrote the 546-line harness on main — caught by diffing before committing; a schema mismatch between golden set and team schema, resolved by converting all 49 items and validating.
- **"Why chunk-level relevance via URL+quote?"** — "Chunk IDs change on re-chunking (Stage 6); URLs and evidence quotes don't. Labels survive re-indexing — that was risk R6 in our plan."
- **"How would you scale the eval to 1,000 questions?"** — "LLM-as-judge calibrated against ≥10 human-graded items (plan §8.4), interleaving for online A/B later."
- **"What next?"** — "Enable real bge-reranker-base in production, tune τ on the trade-off curve, re-run the frozen test once. Longer term: graded relevance labels and inter-annotator agreement on the golden set."

## 7. Numbers to memorize

- **49 items** (19/7/5/5/9/4) · **14 source docs** (10 HTML + 4 PDFs, fetched 2026-10-10) · **116 chunks** dev corpus
- **28 dev / 21 test**, stratified by category, random_state=633, split frozen
- τ=0.5 · 10,000 bootstrap resamples · fuzzy match threshold 0.85 · pool 30 → top 5
- Headline dev results: **B3 = 0.905 Recall@5, 0.823 MRR, 0.829 nDCG@10** vs B2 = 0.810 / 0.622 / 0.640
- Reranker delta: **MRR +0.201 [0.065, 0.352] · nDCG@10 +0.189 [0.047, 0.339]** — both significant; Recall@5 +0.095 not significant; McNemar p=0.69
- Refusals (B3, τ=0.5): 28.6% correct · 9.5% over-refusal
- Error-taxonomy stats: ≥15 failures hand-labeled across 10 categories (retrieval miss, rank failure, chunk boundary, extraction failure, stale content, reranker demotion, generator ignored context, invalid citation, over-refusal, hallucination)
