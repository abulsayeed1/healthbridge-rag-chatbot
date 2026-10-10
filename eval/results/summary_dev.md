# Eval summary — `dev` split (DRAFT: golden set not yet human-verified)

Corpus: 116 chunks from `data/golden_sources/` · embedder: `sentence-transformers/all-MiniLM-L6-v2` · reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2` · tau=0.5 · seed=633

## IR metrics (answerable items)

| system | Recall@5 | Recall@20 | MRR | nDCG@10 | refusal (unans) | false refusal |
|---|---|---|---|---|---|---|
| B0 | 0.714 | 0.857 | 0.486 | 0.534 | n/a | n/a |
| B1 | 0.762 | 0.952 | 0.651 | 0.676 | n/a | n/a |
| B2 | 0.810 | 1.000 | 0.622 | 0.640 | n/a | n/a |
| B3 | 0.905 | 1.000 | 0.823 | 0.829 | 0.286 | 0.095 |

Refusal columns: n/a = no calibrated evidence gate (only B3's sigmoid cross-encoder score supports a fixed tau). tau = 0.5.


## Significance (paired, answerable items, Recall@5 / MRR / nDCG@10)

- **B1_vs_B0** — McNemar exact p=1.0000 (Recall@5 wins B1=4, B0=3)
  - bootstrap_B1_minus_B0_recall@5: delta=0.048, 95% CI [-0.190, 0.286]
  - bootstrap_B1_minus_B0_mrr: delta=0.165, 95% CI [-0.031, 0.351]
  - bootstrap_B1_minus_B0_ndcg@10: delta=0.142, 95% CI [-0.023, 0.312]
- **B2_vs_B1** — McNemar exact p=1.0000 (Recall@5 wins B2=3, B1=2)
  - bootstrap_B2_minus_B1_recall@5: delta=0.048, 95% CI [-0.143, 0.238]
  - bootstrap_B2_minus_B1_mrr: delta=-0.029, 95% CI [-0.175, 0.113]
  - bootstrap_B2_minus_B1_ndcg@10: delta=-0.036, 95% CI [-0.178, 0.097]
- **B3_vs_B2** — McNemar exact p=0.6875 (Recall@5 wins B3=4, B2=2)
  - bootstrap_B3_minus_B2_recall@5: delta=0.095, 95% CI [-0.143, 0.333]
  - bootstrap_B3_minus_B2_mrr: delta=0.201, 95% CI [0.065, 0.352]
  - bootstrap_B3_minus_B2_ndcg@10: delta=0.189, 95% CI [0.047, 0.339]
