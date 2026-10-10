import argparse
import hashlib
import json
import logging
import re
from collections import Counter
from pathlib import Path

import pdfplumber
import trafilatura
import yaml
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b')
EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

def scrub_pii(text: str) -> str:
    if not text: return ""
    text = PHONE_RE.sub("[PHONE_REMOVED]", text)
    text = EMAIL_RE.sub("[EMAIL_REMOVED]", text)
    return text

def extract_html(html_bytes: bytes, url: str) -> dict:
    html_str = html_bytes.decode("utf-8", "ignore")
    soup = BeautifulSoup(html_str, "html.parser")
    
    # Extract title
    title_tag = soup.find("title")
    title = title_tag.text.strip() if title_tag else ""
    
    # Extract tables (convert to Markdown)
    tables_md = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows: continue
        md_table = []
        for row in rows:
            cols = row.find_all(["th", "td"])
            md_row = "| " + " | ".join(c.get_text(strip=True).replace("\n", " ") for c in cols) + " |"
            md_table.append(md_row)
        if md_table:
            # add markdown separator if there's at least one header row
            headers = rows[0].find_all("th")
            if headers:
                md_table.insert(1, "| " + " | ".join(["---"] * len(headers)) + " |")
            tables_md.append("\n".join(md_table))
    
    # Extract main content
    main_text = trafilatura.extract(html_str, include_links=True, include_tables=False)
    if not main_text:
        main_text = soup.get_text(separator="\n", strip=True)
    
    full_text = scrub_pii(main_text)
    if tables_md:
        full_text += "\n\n### Tables\n\n" + "\n\n".join(tables_md)
        
    return {
        "title": scrub_pii(title),
        "text": full_text,
        "page_type": "html"
    }

def extract_pdf(pdf_path: Path) -> dict:
    text_blocks = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_blocks.append(text)
                tables = page.extract_tables()
                for table in tables:
                    if not table: continue
                    md_table = []
                    for i, row in enumerate(table):
                        cleaned_row = [str(c).replace("\n", " ") if c else "" for c in row]
                        md_row = "| " + " | ".join(cleaned_row) + " |"
                        md_table.append(md_row)
                        if i == 0:
                            md_table.append("| " + " | ".join(["---"] * len(row)) + " |")
                    text_blocks.append("\n".join(md_table))
    except Exception as e:
        logger.error(f"PDF extraction failed for {pdf_path}: {e}")
        
    full_text = scrub_pii("\n\n".join(text_blocks))
    return {
        "title": pdf_path.name,
        "text": full_text,
        "page_type": "pdf"
    }

class Extractor:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.raw_dir = Path(cfg["crawl"]["raw_dir"])
        self.norm_dir = Path(cfg["extract"]["normalized_dir"])
        self.norm_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = self.raw_dir / "manifest.jsonl"
        self.max_boilerplate_share = cfg["extract"]["boilerplate_paragraph_max_doc_share"]
        
    def run(self):
        if not self.manifest.exists():
            logger.error("Raw manifest not found. Run crawler first.")
            return

        docs = []
        with open(self.manifest) as f:
            for line in f:
                if line.strip():
                    docs.append(json.loads(line))

        extracted_docs = []
        para_counts = Counter()
        
        logger.info(f"Extracting {len(docs)} documents...")
        for doc in docs:
            raw_file = self.raw_dir / doc["file"]
            if not raw_file.exists():
                continue
            
            if doc["content_type"].startswith("application/pdf"):
                ext_data = extract_pdf(raw_file)
            else:
                ext_data = extract_html(raw_file.read_bytes(), doc["url"])
                
            norm_doc = {
                "doc_id": doc["sha256"],
                "url": doc["url"],
                "title": ext_data.get("title", ""),
                "text": ext_data.get("text", ""),
                "page_type": ext_data.get("page_type", ""),
                "effective_date": doc["crawl_ts"]
            }
            extracted_docs.append(norm_doc)
            
            for para in norm_doc["text"].split("\n"):
                para = para.strip()
                if len(para) > 20: 
                    para_counts[para] += 1
                    
        # Boilerplate removal
        threshold = len(extracted_docs) * self.max_boilerplate_share
        boilerplate = {p for p, c in para_counts.items() if c > threshold}
        logger.info(f"Removing {len(boilerplate)} boilerplate paragraphs...")
        
        norm_manifest_path = self.norm_dir / "normalized_manifest.jsonl"
        with open(norm_manifest_path, "w") as f:
            for doc in extracted_docs:
                clean_paras = []
                for para in doc["text"].split("\n"):
                    if para.strip() not in boilerplate:
                        clean_paras.append(para)
                
                doc["text"] = "\n".join(clean_paras)
                
                doc_path = self.norm_dir / f"{doc['doc_id']}.json"
                doc_path.write_text(json.dumps(doc, indent=2))
                
                manifest_entry = {
                    "doc_id": doc["doc_id"],
                    "url": doc["url"],
                    "file": f"{doc['doc_id']}.json"
                }
                f.write(json.dumps(manifest_entry) + "\n")
                
        logger.info(f"Finished extracting {len(extracted_docs)} documents.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    Extractor(cfg).run()

if __name__ == "__main__":
    main()
