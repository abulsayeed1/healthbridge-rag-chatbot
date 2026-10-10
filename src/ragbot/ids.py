"""Deterministic document and chunk IDs (proposal §5.2).

doc_id   = sha256(canonical_url)[:16]
chunk_id = f"{doc_id}::{strategy_tag}::{ordinal:04d}"
"""
from __future__ import annotations

import hashlib

from ragbot.scrape.crawler import canonicalize


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_doc_id(url: str) -> str:
    return sha256_text(canonicalize(url))[:16]


def make_chunk_id(doc_id: str, strategy_tag: str, ordinal: int) -> str:
    if "::" in strategy_tag:
        raise ValueError("strategy_tag must not contain '::'")
    return f"{doc_id}::{strategy_tag}::{ordinal:04d}"


def parse_chunk_id(chunk_id: str) -> tuple[str, str, int]:
    doc_id, tag, ordinal = chunk_id.split("::")
    return doc_id, tag, int(ordinal)
