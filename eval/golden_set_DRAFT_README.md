# Golden Set — DRAFT, pending human verification

`golden_set.jsonl` contains **49 draft items** (19 single-hop, 7 multi-hop, 5 comparative,
5 temporal, 9 unanswerable, 4 ambiguous/adversarial) matching the §8.1 targets.

## Provenance (read this first)

These items were **AI-drafted on 2026-10-10 from the live UCSF Health pages** fetched that day
(copies in `data/golden_sources/` — gitignored, so verify against the live URLs below):

- `/patients-visitors/billing-insurance/help-paying-your-bill/`
- `/patients-visitors/billing-insurance/health-insurance/` (Reviewed May 27, 2026)
- `/patients-visitors/medical-records/`
- `/patients-visitors/second-opinion/`
- `/patients-visitors/billing-insurance/no-surprises-billing-act/`
- `/patients-visitors/visitors/`, `/your-hospital-stay/`, `/support-services/`, `/appointments/`
- PDFs: `patient_financial_assistance_policy_30407.pdf`, `self_pay_discount_policy_30406.pdf`,
  `debt-collection-030408.pdf`, `financial_assistance_application.pdf` (UCSF CDN)

Our proposal requires: **"No unverified AI-drafted items are allowed"** and every item verified
against the page **by a different member than its author**. So every item below must go through
the verification pass before the file is committed to `eval/golden_set.jsonl` via a reviewed PR.
Add an AI-assistance note to the report/README when committing (same as the proposal's AI Disclosure).

## Verification workflow (do this today, ~15 min per member)

1. **Claim** your 7 items below (round-robin; swap freely on the board to get a category mix you like).
2. **Verify each item** by opening its `source_urls` and checking:
   - The question is actually answerable from that page/PDF (or genuinely absent from the corpus, for `unanswerable`).
   - The `gold_answer` is factually correct — fix wording if needed.
   - The `evidence_quote` appears **verbatim** on the page (≤25 words). Tables quote poorly; re-quote cleanly if needed.
   - For `unanswerable`: spend 2–3 minutes actually searching for the answer (site, sitemap, PDFs); confirm `searched_for` is honest.
   - For `ambiguous_adversarial`: confirm the `gold_answer` describes the behavior we want (clarify / refuse / redirect).
3. **Fill in** `author` (you) and `verifier` (a different member — use your review pairing:
   Shabbar↔Ravalika, Hasan↔Harsha, Sai↔Manish, Zaineb↔Shabbar), set `verified_at` to today.
4. **Commit** through a reviewed PR. The commit hash is our proof of authorship-before-tuning (§8.1).

## Claim assignments (round-robin over the 49 items)

| Member | Items (7 each) |
|---|---|
| Shabbar | G001, G008, G015, G022, G029, G036, G043 |
| Ravalika | G002, G009, G016, G023, G030, G037, G044 |
| Hasan | G003, G010, G017, G024, G031, G038, G045 |
| Harsha | G004, G011, G018, G025, G032, G039, G046 |
| Sai | G005, G012, G019, G026, G033, G040, G047 |
| Manish | G006, G013, G020, G027, G034, G041, G048 |
| Zaineb | G007, G014, G021, G028, G035, G042, G049 |

## Spares (if an item fails verification, swap in one of these)

- **Temporal:** "When was the Health Insurance page last reviewed?" → "Reviewed May 27, 2026" (`/health-insurance/`).
- **Temporal:** "When was the Patient Financial Assistance Policy last revised?" → "Revised October 2020…" (FA policy PDF, revision history section).
- **Single-hop:** "Where do I mail the financial assistance application?" → 6425 Christie Avenue Suite 500, Emeryville, CA 94608 (FA application PDF).
- **Single-hop:** "Where can I get my radiology images on CD?" → free CD via release form, mailed 5–7 business days (`/medical-records/`).
- **Unanswerable:** "What is the weather in San Francisco today?" — not in corpus.

## Schema

Each line of `golden_set.jsonl`:
`id, category, question, gold_answer, source_urls[], evidence_quote (null for unanswerable/adversarial), searched_for (unanswerable only), author, verifier, verified_at`

Relevance for eval is keyed to **source URL + evidence quote** (fuzzy ≥ 0.85 token-set ratio),
not chunk IDs — so labels survive re-chunking (risk R6).
