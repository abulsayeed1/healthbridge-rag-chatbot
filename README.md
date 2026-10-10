# UCSF Health Patient Navigator — RAG Chatbot (Team HealthBridge)

This chatbot answers **administrative** patient questions (billing, insurance, financial assistance, visitors, medical records, support services, locations). It uses only public pages scraped from `ucsfhealth.org`, cites a source for every claim, and refuses when the corpus does not support an answer.

> Unofficial student project. Not affiliated with UCSF Health. Informational only. This is not medical, legal or financial advice.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp .env.example .env        # add OPENAI_API_KEY and CRAWLER_CONTACT_EMAIL
pytest -q                   # ID-scheme tests
```

## Pipeline commands

| Stage | Command | Status |
|---|---|---|
| 1 Scrape | `python -m ragbot.scrape.crawler --config config/config.yaml` | implemented |
| 2 Extract | `python -m ragbot.extract.extractor` | stub |
| 3 Chunk | `python -m ragbot.chunk.chunkers` | stub |
| 4–5 Embed + index | `python -m ragbot.embed.embedder` | stub |
| 6 Re-chunk | `python -m ragbot.store.rechunk` | stub |
| 7–8 Retrieve + rerank | `python -m ragbot.retrieve.retrievers` | stub |
| 9 Generate / UI | `streamlit run app/streamlit_app.py` | stub |
| Eval | `python -m ragbot.eval.run_eval` | stub |

## Repository layout

```
config/       single config.yaml for every stage
src/ragbot/   one sub-package per pipeline stage
app/          Streamlit chat UI
eval/         golden set (+ schema) and split
reports/      00_proposal … 07_ethics
scripts/      GitHub setup
data/         raw / normalized / chunks / index (git-ignored)
```

## Team workflow

- `main` is protected. Work on short-lived branches (`scrape/crawler`, `chunk/structure-aware`, …) and merge through a PR with ≥1 teammate approval.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`).
- One-time setup: `./scripts/setup_github.sh <owner>`

## Reports

See [`reports/`](reports/). The design is in [`00_proposal.md`](reports/00_proposal.md).

## Known limitations

To be completed at the end of the project.

## AI usage

| Tool | Used for | Artifacts | Human review |
|---|---|---|---|
| Antigravity agent (Claude) | Drafted the proposal and initial scaffolding (crawler, ID scheme, config, setup script) | `reports/00_proposal.md`, `src/ragbot/scrape/crawler.py`, `src/ragbot/ids.py` | Reviewed and edited by the team |

Golden-set items are authored and verified by humans only.
