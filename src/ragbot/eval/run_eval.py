"""Evaluation harness: B0-B3 baselines, IR metrics, refusal rates, bootstrap CIs, McNemar.

Owner: Member 3 (Manish). Branch: eval/harness.
See reports/00_proposal.md and reports/06_final_performance.md for the design and results.

What it measures
----------------
Four retrieval configurations ("systems"), all over the same chunk corpus built from
`data/golden_sources/*.txt` (the live UCSF pages the golden set was authored from):

    B0  BM25 lexical only                  (Stage 7 sparse, in isolation)
    B1  Dense embeddings only              (Stage 6 vector search, in isolation)
    B2  Hybrid: BM25 + dense, RRF fusion   (the "B2 baseline" of the TPM plan)
    B3  B2 + Stage 8 cross-encoder rerank  (full retrieval stack, sigmoid scores)

The B3 cross-encoder lives here so the harness can quantify what Stage 8 *should* deliver;
production `rerank/reranker.py` currently bypasses its model and must adopt the same scorer
before Sunday's run.

Protocol (proposal §8.1)
------------------------
- Golden set: `eval/golden_set.jsonl` (49 draft items — DO NOT treat results as final until
  the human verification pass is done).
- Split: 60/40 dev/test, stratified by category, seed 633. Partitions are written to
  `eval/golden_set.dev.jsonl` / `eval/golden_set.test.jsonl` on first run and reused
  afterwards, so dev tuning never leaks into test. The test split runs once, Sunday,
  against the frozen `v-final` tag.
- Relevance (survives re-chunking): a hit is relevant iff its source URL is in the item's
  `source_urls` AND its text contains the `evidence_quote` with token-set similarity >= 0.85.
- IR metrics (answerable items only): Recall@5, Recall@20, MRR, nDCG@10.
- Refusal: evidence gate on the best score in the top-5 — refuse when it is below `tau`.
  A calibrated gate only exists for B3 (sigmoid cross-encoder probability, i.e. the
  production Stage 8 gate). BM25/RRF/embedding scores are not probabilities, so B0-B2
  refusal rates are not comparable and are reported as n/a. Refusal rate on
  unanswerable/ambiguous items (want HIGH) and false-refusal rate on answerable items
  (want LOW) are both reported.
- Significance: paired bootstrap CIs (10,000 resamples, seed 633) on system deltas, and
  exact McNemar tests on per-item Recall@5 outcomes for adjacent system pairs.

Usage
-----
    python src/ragbot/eval/run_eval.py --split dev
    python src/ragbot/eval/run_eval.py --split test --bootstrap 10000
    python src/ragbot/eval/run_eval.py --split dev --systems B0,B2 --no-bootstrap

Outputs: `eval/results/<split>_metrics.json` and `eval/results/summary_<split>.md`.

Defaults run fully offline (all-MiniLM-L6-v2 is small and commonly cached). For the
production run set `embedding_model` / `rerank_model` in `eval/eval_config.yaml`
(e.g. BAAI/bge-* per the proposal).
"""

import argparse
import json
import math
import random
import re
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULTS = {
    "corpus_dir": "data/golden_sources",
    "golden_set": "eval/golden_set.jsonl",
    "out_dir": "eval/results",
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_query_prefix": "",
    "rerank_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "rerank_max_length": 512,
    "pool_size": 30,          # 30-candidate pool per the proposal
    "top_k": 5,               # final evidence set size
    "rrf_k": 60,
    "chunk_tokens": 256,
    "chunk_overlap": 50,
    "tau": 0.5,               # evidence-gate threshold on sigmoid scores
    "split_seed": 633,
    "bootstrap_n": 10000,
    "bootstrap_seed": 633,
}

# file stem in data/golden_sources -> canonical source URL
STEM_TO_URL = {
    "patients-visitors_appointments": "https://www.ucsfhealth.org/patients-visitors/appointments/",
    "patients-visitors_billing-insurance": "https://www.ucsfhealth.org/patients-visitors/billing-insurance/",
    "patients-visitors_billing-insurance_health-insurance": "https://www.ucsfhealth.org/patients-visitors/billing-insurance/health-insurance/",
    "patients-visitors_billing-insurance_help-paying-your-bill": "https://www.ucsfhealth.org/patients-visitors/billing-insurance/help-paying-your-bill/",
    "patients-visitors_billing-insurance_no-surprises-billing-act": "https://www.ucsfhealth.org/patients-visitors/billing-insurance/no-surprises-billing-act/",
    "patients-visitors_medical-records": "https://www.ucsfhealth.org/patients-visitors/medical-records/",
    "patients-visitors_second-opinion": "https://www.ucsfhealth.org/patients-visitors/second-opinion/",
    "patients-visitors_support-services": "https://www.ucsfhealth.org/patients-visitors/support-services/",
    "patients-visitors_visitors": "https://www.ucsfhealth.org/patients-visitors/visitors/",
    "patients-visitors_your-hospital-stay": "https://www.ucsfhealth.org/patients-visitors/your-hospital-stay/",
    "visitors2": "https://www.ucsfhealth.org/patients-visitors/visitors/",
    "debt-collection-030408": "https://edge.sitecorecloud.io/ucsfhealth1487c-ucsfplatfor7e11-prod0cc0-65a9/media/project/valcore/live/ucsf/pdf/financial-pdfs/debt-collection-030408.pdf",
    "financial_assistance_application": "https://edge.sitecorecloud.io/ucsfhealth1487c-ucsfplatfor7e11-prod0cc0-65a9/media/project/valcore/live/ucsf/pdf/financial-pdfs/financial_assistance_application.pdf",
    "patient_financial_assistance_policy_30407": "https://edge.sitecorecloud.io/ucsfhealth1487c-ucsfplatfor7e11-prod0cc0-65a9/media/project/valcore/live/ucsf/pdf/financial-pdfs/patient_financial_assistance_policy_30407.pdf",
    "self_pay_discount_policy_30406": "https://edge.sitecorecloud.io/ucsfhealth1487c-ucsfplatfor7e11-prod0cc0-65a9/media/project/valcore/live/ucsf/pdf/financial-pdfs/self_pay_discount_policy_30406.pdf",
}


# ---------------------------------------------------------------- golden set & split

def load_golden_set(path: Path) -> list[dict]:
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def stratified_split(items: list[dict], dev_frac: float, seed: int) -> tuple[list[dict], list[dict]]:
    """Deterministic 60/40 split stratified by category. No sklearn needed."""
    rng = random.Random(seed)
    by_cat: dict[str, list[dict]] = {}
    for it in items:
        by_cat.setdefault(it["category"], []).append(it)
    dev_ids, test_ids = set(), set()
    for cat in sorted(by_cat):
        ids = sorted(it["id"] for it in by_cat[cat])
        rng.shuffle(ids)
        n_dev = round(dev_frac * len(ids))
        dev_ids.update(ids[:n_dev])
        test_ids.update(ids[n_dev:])
    dev = [it for it in items if it["id"] in dev_ids]
    test = [it for it in items if it["id"] in test_ids]
    return dev, test


def get_split(items: list[dict], split: str, cfg: dict, out_dir: Path) -> list[dict]:
    """Frozen partition: reuse eval/golden_set.{dev,test}.jsonl if present, else create."""
    dev_path = out_dir.parent / "golden_set.dev.jsonl"
    test_path = out_dir.parent / "golden_set.test.jsonl"
    if not (dev_path.exists() and test_path.exists()):
        dev, test = stratified_split(items, 0.6, cfg["split_seed"])
        for p, part in ((dev_path, dev), (test_path, test)):
            with open(p, "w", encoding="utf-8") as f:
                for it in part:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
        print(f"[split] wrote frozen partitions: {len(dev)} dev / {len(test)} test "
              f"(seed {cfg['split_seed']})")
    part_path = dev_path if split == "dev" else test_path
    return [json.loads(l) for l in open(part_path, encoding="utf-8")]


# ---------------------------------------------------------------- corpus

def build_corpus(cfg: dict) -> list[dict]:
    """Chunk every *.txt golden source; one record per chunk with its canonical URL."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    corpus_dir = REPO_ROOT / cfg["corpus_dir"]
    chunks = []
    files = sorted(corpus_dir.glob("*.txt"))
    for txt in files:
        stem = txt.stem
        url = STEM_TO_URL.get(stem)
        if url is None:
            print(f"[corpus] WARNING: no URL mapping for {stem}, its chunks can never match")
        text = txt.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            continue
        tokens = enc.encode(text)
        i, idx = 0, 0
        while i < len(tokens):
            piece = enc.decode(tokens[i:i + cfg["chunk_tokens"]]).strip()
            if piece:
                chunks.append({"chunk_id": f"{stem}::{idx}", "url": url, "text": piece})
            if i + cfg["chunk_tokens"] >= len(tokens):
                break
            i += cfg["chunk_tokens"] - cfg["chunk_overlap"]
            idx += 1
    print(f"[corpus] {len(chunks)} chunks from {len(files)} source files")
    return chunks


# ---------------------------------------------------------------- relevance & metrics

def token_set_similarity(quote: str, text: str) -> float:
    """Fraction of the quote's tokens found in the text, in [0,1].

    Quote-anchored token-set containment: equals 1.0 when every quote token appears in
    the text, matching the intent of rapidfuzz `token_set_ratio >= 0.85` (quote ⊆ chunk,
    tolerant of small wording drift) without penalising chunk length.
    """
    a = set(re.findall(r"\w+", quote.lower()))
    b = set(re.findall(r"\w+", text.lower()))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def is_relevant(item: dict, hit: dict, threshold: float = 0.85) -> bool:
    quotes = item.get("evidence_quotes") or []
    if not quotes:
        return False
    if hit.get("url") not in item.get("source_urls", []):
        return False
    return any(token_set_similarity(q, hit["text"]) >= threshold for q in quotes)


def expects_answer(item: dict) -> bool:
    """'answer' items drive IR metrics; refuse/clarify items drive the refusal gate."""
    return item.get("expected_behavior", "answer") == "answer"


def per_item_outcomes(ranked_hits: list[dict], item: dict) -> dict:
    """Per-item metric values for one ranked hit list."""
    rel_flags = [is_relevant(item, h) for h in ranked_hits]
    first_rel = next((i + 1 for i, r in enumerate(rel_flags) if r), 0)  # 1-based, 0 = none
    n_rel = sum(rel_flags)
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(rel_flags[:10]) if r)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(n_rel, 10)))
    return {
        "first_rel_rank": first_rel,
        "recall@5": 1.0 if 0 < first_rel <= 5 else 0.0,
        "recall@20": 1.0 if 0 < first_rel <= 20 else 0.0,
        "mrr": 1.0 / first_rel if first_rel else 0.0,
        "ndcg@10": dcg / idcg if idcg else 0.0,
        "n_relevant_in_pool": n_rel,
    }


def aggregate(outcomes: list[dict]) -> dict:
    n = len(outcomes) or 1
    return {
        "recall@5": sum(o["recall@5"] for o in outcomes) / n,
        "recall@20": sum(o["recall@20"] for o in outcomes) / n,
        "mrr": sum(o["mrr"] for o in outcomes) / n,
        "ndcg@10": sum(o["ndcg@10"] for o in outcomes) / n,
        "n_items": len(outcomes),
    }


# ---------------------------------------------------------------- systems (B0-B3)

class BM25System:
    name = "B0"

    def __init__(self, corpus, cfg):
        from rank_bm25 import BM25Okapi
        self.cfg = cfg
        self.corpus = corpus
        print(f"[B0] BM25 over {len(corpus)} chunks")
        self.bm25 = BM25Okapi([c["text"].split(" ") for c in corpus])

    def search(self, query: str) -> list[dict]:
        scores = self.bm25.get_scores(query.split(" "))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        hits = []
        for i in order[: self.cfg["pool_size"]]:
            if scores[i] <= 0:
                continue
            hits.append({**self.corpus[i], "score": float(scores[i])})
        return hits


class DenseSystem:
    name = "B1"

    def __init__(self, corpus, cfg):
        from sentence_transformers import SentenceTransformer
        import numpy as np
        self.np = np
        self.cfg = cfg
        self.corpus = corpus
        print(f"[B1] loading embedding model {cfg['embedding_model']} ...")
        self.model = SentenceTransformer(cfg["embedding_model"])
        self.emb = self.model.encode(
            [c["text"] for c in corpus], batch_size=32,
            normalize_embeddings=True, show_progress_bar=False)

    def search(self, query: str) -> list[dict]:
        q = self.cfg["embedding_query_prefix"] + query
        q_emb = self.model.encode(q, normalize_embeddings=True)
        sims = self.emb @ self.np.asarray(q_emb)
        order = self.np.argsort(-sims)[: self.cfg["pool_size"]]
        return [{**self.corpus[int(i)], "score": float(sims[i])} for i in order]


def rrf_fuse(hit_lists: list[list[dict]], rrf_k: int, pool: int) -> list[dict]:
    scores, by_id = {}, {}
    for hits in hit_lists:
        for rank, h in enumerate(hits):
            scores[h["chunk_id"]] = scores.get(h["chunk_id"], 0.0) + 1.0 / (rrf_k + rank + 1)
            by_id[h["chunk_id"]] = h
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:pool]
    out = []
    for cid, s in fused:
        h = dict(by_id[cid])
        h["rrf_score"] = s
        out.append(h)
    return out


class HybridSystem:
    """B2: BM25 + dense fused with RRF (mirrors production Retriever.search(mode='hybrid'))."""
    name = "B2"

    def __init__(self, bm25: BM25System, dense: DenseSystem, cfg):
        self.bm25, self.dense, self.cfg = bm25, dense, cfg

    def search(self, query: str) -> list[dict]:
        return rrf_fuse([self.bm25.search(query), self.dense.search(query)],
                        self.cfg["rrf_k"], self.cfg["pool_size"])


class RerankSystem:
    """B3: B2 pool scored by a cross-encoder; sigmoid scores feed the evidence gate."""
    name = "B3"

    def __init__(self, hybrid: HybridSystem, cfg):
        self.hybrid = hybrid
        self.cfg = cfg
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            print(f"[B3] loading cross-encoder {self.cfg['rerank_model']} ...")
            self._model = CrossEncoder(self.cfg["rerank_model"],
                                       max_length=self.cfg["rerank_max_length"])

    def search(self, query: str) -> list[dict]:
        self._load()
        hits = self.hybrid.search(query)
        if not hits:
            return []
        import numpy as np
        pairs = [(query, h["text"]) for h in hits]
        raw = self._model.predict(pairs, batch_size=32, show_progress_bar=False)
        raw = self.np_asarray(raw)
        # some CE heads emit logits, some probabilities; normalise to [0,1]
        if raw.min() < 0.0 or raw.max() > 1.0:
            raw = 1.0 / (1.0 + np.exp(-raw))
        for h, s in zip(hits, raw):
            h["rerank_score"] = float(s)
        hits.sort(key=lambda h: h["rerank_score"], reverse=True)
        return hits

    @staticmethod
    def np_asarray(raw):
        import numpy as np
        return np.asarray(raw, dtype=float).ravel()


def gate_scores(hits: list[dict]) -> list[float] | None:
    """Top-5 sigmoid evidence scores for the B3 refusal gate; None for uncalibrated systems.

    BM25/RRF/embedding scores are not probabilities, so only B3's cross-encoder output
    supports a fixed `tau` threshold.
    """
    if not hits:
        return []
    scores = [h.get("rerank_score") for h in hits[:5]]
    return scores if all(s is not None for s in scores) else None


# ---------------------------------------------------------------- significance tests

def paired_bootstrap(deltas: list[float], n_resamples: int, seed: int) -> dict:
    import numpy as np
    rng = np.random.default_rng(seed)
    arr = np.asarray(deltas, dtype=float)
    idx = rng.integers(0, len(arr), size=(n_resamples, len(arr)))
    means = arr[idx].mean(axis=1)
    return {
        "mean_delta": float(arr.mean()),
        "ci95_low": float(np.percentile(means, 2.5)),
        "ci95_high": float(np.percentile(means, 97.5)),
    }


def mcnemar_exact(win_a: int, win_b: int) -> float:
    """Two-sided exact McNemar p-value on discordant pairs (a wins vs b wins)."""
    n = win_a + win_b
    if n == 0:
        return 1.0
    k = min(win_a, win_b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


# ---------------------------------------------------------------- main

def fmt(x: float) -> str:
    return f"{x:.3f}"


def fmt_or_na(x: float | None) -> str:
    return "n/a" if x is None else fmt(x)


def main() -> None:
    ap = argparse.ArgumentParser(description="HealthBridge eval harness (B0-B3)")
    ap.add_argument("--split", choices=["dev", "test", "both"], default="dev")
    ap.add_argument("--systems", default="B0,B1,B2,B3")
    ap.add_argument("--bootstrap", type=int, default=None, help="override resample count")
    ap.add_argument("--no-bootstrap", action="store_true")
    ap.add_argument("--corpus-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--config", default="eval/eval_config.yaml")
    args = ap.parse_args()

    cfg = dict(DEFAULTS)
    cfg_path = REPO_ROOT / args.config
    if cfg_path.exists():
        import yaml
        cfg.update(yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {})
    if args.corpus_dir:
        cfg["corpus_dir"] = args.corpus_dir
    if args.out_dir:
        cfg["out_dir"] = args.out_dir
    if args.bootstrap is not None:
        cfg["bootstrap_n"] = args.bootstrap
    if args.no_bootstrap:
        cfg["bootstrap_n"] = 0

    items = load_golden_set(REPO_ROOT / cfg["golden_set"])
    out_dir = REPO_ROOT / cfg["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    corpus = build_corpus(cfg)

    # build system objects once; B2/B3 reuse the B0/B1 components
    wanted = [s.strip().upper() for s in args.systems.split(",")]
    bm25 = BM25System(corpus, cfg) if any(s in wanted for s in ("B0", "B2", "B3")) else None
    dense = DenseSystem(corpus, cfg) if any(s in wanted for s in ("B1", "B2", "B3")) else None
    systems = {}
    if "B0" in wanted:
        systems["B0"] = bm25
    if "B1" in wanted:
        systems["B1"] = dense
    if "B2" in wanted:
        systems["B2"] = HybridSystem(bm25, dense, cfg)
    if "B3" in wanted:
        systems["B3"] = RerankSystem(systems["B2"], cfg)

    for split in (["dev", "test"] if args.split == "both" else [args.split]):
        part = get_split(items, split, cfg, out_dir)
        answerable = [it for it in part if expects_answer(it)]
        refusal_expected = [it for it in part if not expects_answer(it)]
        print(f"\n===== split={split}: {len(part)} items "
              f"({len(answerable)} answerable / {len(refusal_expected)} refusal-expected) =====")

        split_results = {"config": cfg, "systems": {}}
        per_item = {}
        for name in [s for s in ("B0", "B1", "B2", "B3") if s in systems]:
            t0 = time.time()
            outcomes, refusal_counts = [], {"correct": 0, "false_refusal": 0, "n_a": 0}
            for it in part:
                hits = systems[name].search(it["question"])
                outcomes.append(per_item_outcomes(hits, it))
                scores = gate_scores(hits)
                refused = (not scores) or max(scores) < cfg["tau"]
                if scores is None:
                    refusal_counts["n_a"] += 1  # no calibrated gate (B0-B2)
                elif expects_answer(it):
                    refusal_counts["false_refusal"] += int(refused)
                else:
                    refusal_counts["correct"] += int(refused)
            ans_outcomes = [o for o, it in zip(outcomes, part) if expects_answer(it)]
            agg = aggregate(ans_outcomes)
            n_exp = len(refusal_expected) or 1
            n_ans = len(answerable) or 1
            if refusal_counts["n_a"]:
                agg["refusal_rate_unanswerable"] = None
                agg["false_refusal_rate_answerable"] = None
            else:
                agg["refusal_rate_unanswerable"] = refusal_counts["correct"] / n_exp
                agg["false_refusal_rate_answerable"] = refusal_counts["false_refusal"] / n_ans
            per_item[name] = {it["id"]: o for o, it in zip(outcomes, part)}
            split_results["systems"][name] = agg
            print(f"[{name}] R@5={fmt(agg['recall@5'])} R@20={fmt(agg['recall@20'])} "
                  f"MRR={fmt(agg['mrr'])} nDCG@10={fmt(agg['ndcg@10'])} "
                  f"refuse(unans)={fmt_or_na(agg['refusal_rate_unanswerable'])} "
                  f"falseRefuse={fmt_or_na(agg['false_refusal_rate_answerable'])} "
                  f"({time.time() - t0:.1f}s)")

        # significance: adjacent system pairs on per-item metrics (answerable items only)
        ans_ids = [it["id"] for it in part if expects_answer(it)]
        sig = {}
        for a, b in (("B0", "B1"), ("B1", "B2"), ("B2", "B3")):
            if a not in per_item or b not in per_item:
                continue
            entry = {}
            for metric in ("recall@5", "mrr", "ndcg@10"):
                deltas = [per_item[b][i][metric] - per_item[a][i][metric] for i in ans_ids]
                entry[f"bootstrap_{b}_minus_{a}_{metric}"] = paired_bootstrap(
                    deltas, cfg["bootstrap_n"] or 1, cfg["bootstrap_seed"])
            recall_a = [per_item[a][i]["recall@5"] for i in ans_ids]
            recall_b = [per_item[b][i]["recall@5"] for i in ans_ids]
            win_a = sum(1 for x, y in zip(recall_a, recall_b) if x > y)
            win_b = sum(1 for x, y in zip(recall_a, recall_b) if y > x)
            entry["mcnemar"] = {"wins_" + a: win_a, "wins_" + b: win_b,
                                "p_exact": mcnemar_exact(win_a, win_b)}
            sig[f"{b}_vs_{a}"] = entry

        split_results["significance"] = sig

        # markdown summary (inputs for report 06)
        lines = [f"# Eval summary — `{split}` split (DRAFT: golden set not yet human-verified)",
                 "",
                 f"Corpus: {len(corpus)} chunks from `data/golden_sources/` · "
                 f"embedder: `{cfg['embedding_model']}` · reranker: `{cfg['rerank_model']}` · "
                 f"tau={cfg['tau']} · seed={cfg['split_seed']}",
                 "",
                 "## IR metrics (answerable items)", "",
                 "| system | Recall@5 | Recall@20 | MRR | nDCG@10 | refusal (unans) | false refusal |",
                 "|---|---|---|---|---|---|---|"]
        for name, agg in split_results["systems"].items():
            lines.append(
                f"| {name} | {fmt(agg['recall@5'])} | {fmt(agg['recall@20'])} | "
                f"{fmt(agg['mrr'])} | {fmt(agg['ndcg@10'])} | "
                f"{fmt_or_na(agg['refusal_rate_unanswerable'])} | "
                f"{fmt_or_na(agg['false_refusal_rate_answerable'])} |")
        lines += [
            "",
            "Refusal columns: n/a = no calibrated evidence gate (only B3's sigmoid "
            "cross-encoder score supports a fixed tau). tau = "
            f"{cfg['tau']}.",
            "",
        ]
        lines += ["", "## Significance (paired, answerable items, Recall@5 / MRR / nDCG@10)", ""]
        for pair, e in sig.items():
            m = e["mcnemar"]
            a, b = pair.split("_vs_")
            lines.append(f"- **{pair}** — McNemar exact p={m['p_exact']:.4f} "
                         f"(Recall@5 wins {a}={m['wins_' + a]}, {b}={m['wins_' + b]})")
            for k, v in e.items():
                if k.startswith("bootstrap_"):
                    lines.append(f"  - {k}: delta={fmt(v['mean_delta'])}, "
                                 f"95% CI [{fmt(v['ci95_low'])}, {fmt(v['ci95_high'])}]")
        summary_path = out_dir / f"summary_{split}.md"
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        (out_dir / f"{split}_metrics.json").write_text(
            json.dumps(split_results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[out] {out_dir / (split + '_metrics.json')}")
        print(f"[out] {summary_path}")

    return None


if __name__ == "__main__":
    main()
