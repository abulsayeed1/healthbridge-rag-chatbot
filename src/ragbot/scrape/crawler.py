"""Stage 1 — Polite crawler for ucsfhealth.org.

Guarantees (spec §2 Stage 1, §7):
  * robots.txt parsed and honored in code before every request
  * global rate limit <= 1 request/second (robots Crawl-delay wins if larger)
  * descriptive User-Agent containing a contact email
  * raw bytes saved to disk with URL, timestamp and SHA-256 BEFORE any parsing
  * hard deny-list for directory / login pages (no PII)

Usage:
    python -m ragbot.scrape.crawler --config config/config.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse, urlunparse

import requests
import yaml
from dotenv import load_dotenv

LINK_RE = re.compile(r'href="([^"#]+)"', re.IGNORECASE)
LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def canonicalize(url: str) -> str:
    """Lowercase scheme/host, drop fragment, drop trailing slash (except root)."""
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query, ""))


class PoliteCrawler:
    def __init__(self, cfg: dict):
        c = cfg["crawl"]
        self.cfg = c
        self.base = urlparse(c["base_url"]).netloc
        email = os.getenv("CRAWLER_CONTACT_EMAIL", "unknown@example.edu")
        self.ua = c["user_agent"].format(email=email)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = self.ua
        self.raw_dir = Path(c["raw_dir"])
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.raw_dir / "manifest.jsonl"
        self.skip_log = self.raw_dir / "skipped.jsonl"
        self.robots: dict[str, robotparser.RobotFileParser] = {}
        self.last_request = 0.0
        self.seen: set[str] = self._load_seen()

    # ---------- politeness ----------
    def _robots_for(self, url: str) -> robotparser.RobotFileParser:
        host = urlparse(url).netloc
        if host not in self.robots:
            rp = robotparser.RobotFileParser()
            robots_url = f"https://{host}/robots.txt"
            rp.set_url(robots_url)
            try:
                r = self.session.get(robots_url, timeout=self.cfg["timeout_seconds"])
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                elif r.status_code in (401, 403):
                    rp.disallow_all = True
            except Exception:
                rp.disallow_all = True  # fail closed
            self.robots[host] = rp
        return self.robots[host]

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(self.ua, url)

    def _throttle(self, url: str) -> None:
        delay = float(self.cfg["min_delay_seconds"])
        cd = self._robots_for(url).crawl_delay(self.ua)
        if cd:
            delay = max(delay, float(cd))
        wait = self.last_request + delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.last_request = time.monotonic()

    # ---------- scope ----------
    def in_scope(self, url: str) -> bool:
        p = urlparse(url)
        if p.query:  # robots.txt disallows /*?* on this site
            return False
        if p.netloc in self.cfg["pdf_hosts"]:
            return p.path.lower().endswith(".pdf")
        if p.netloc != self.base:
            return False
        if any(p.path.startswith(d) for d in self.cfg["deny_prefixes"]):
            return False
        return p.path == "/" or any(p.path.startswith(a) for a in self.cfg["allow_prefixes"])

    # ---------- storage ----------
    def _load_seen(self) -> set[str]:
        if not self.manifest_path.exists():
            return set()
        with self.manifest_path.open() as f:
            return {json.loads(line)["url"] for line in f if line.strip()}

    def _log(self, path: Path, rec: dict) -> None:
        with path.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def fetch(self, url: str) -> bytes | None:
        if not self.allowed(url):
            self._log(self.skip_log, {"url": url, "reason": "robots"})
            return None
        for attempt in range(3):
            self._throttle(url)
            try:
                r = self.session.get(url, timeout=self.cfg["timeout_seconds"])
            except requests.RequestException as e:
                self._log(self.skip_log, {"url": url, "reason": f"error:{e.__class__.__name__}"})
                time.sleep(2 ** (attempt + 1))
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** (attempt + 1))
                continue
            ctype = r.headers.get("Content-Type", "").split(";")[0].strip()
            body = r.content
            sha = hashlib.sha256(body).hexdigest()
            ext = "pdf" if "pdf" in ctype else "html"
            (self.raw_dir / f"{sha}.{ext}").write_bytes(body)  # raw bytes BEFORE parsing
            self._log(self.manifest_path, {
                "url": canonicalize(url),
                "final_url": canonicalize(r.url),
                "status": r.status_code,
                "content_type": ctype,
                "sha256": sha,
                "bytes": len(body),
                "file": f"{sha}.{ext}",
                "crawl_ts": datetime.now(timezone.utc).isoformat(),
            })
            return body if r.status_code == 200 else None
        self._log(self.skip_log, {"url": url, "reason": "retries_exhausted"})
        return None

    # ---------- crawl ----------
    def seed_urls(self) -> list[str]:
        body = self.fetch(self.cfg["sitemap"]) or b""
        urls = [canonicalize(u) for u in LOC_RE.findall(body.decode("utf-8", "ignore"))]
        urls = [u for u in urls if self.in_scope(u)]
        locs = [u for u in urls if urlparse(u).path.startswith("/locations")]
        other = [u for u in urls if u not in set(locs)]
        rng = random.Random(633)
        locs = rng.sample(locs, min(len(locs), self.cfg["locations_sample_size"]))
        return other + locs

    def run(self) -> None:
        queue = self.seed_urls()
        count = len(self.seen)
        while queue and count < self.cfg["max_documents"]:
            url = queue.pop(0)
            if url in self.seen:
                continue
            self.seen.add(url)
            body = self.fetch(url)
            if body is None:
                continue
            count += 1
            if url.lower().endswith(".pdf"):
                continue
            html = body.decode("utf-8", "ignore")
            m = TITLE_RE.search(html)
            title = (m.group(1) if m else "").lower()
            if any(p in title for p in self.cfg["deny_title_patterns"]):
                self._log(self.skip_log, {"url": url, "reason": "deny_title"})
                continue
            for href in LINK_RE.findall(html):
                nxt = canonicalize(urljoin(url, href))
                if nxt not in self.seen and self.in_scope(nxt):
                    # PDFs first so the >=5 PDF minimum is met early
                    (queue.insert(0, nxt) if nxt.endswith(".pdf") else queue.append(nxt))
            if count % 25 == 0:
                print(f"[crawl] {count} documents saved")
        print(f"[crawl] done: {count} documents in {self.raw_dir}")


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    PoliteCrawler(cfg).run()


if __name__ == "__main__":
    main()
