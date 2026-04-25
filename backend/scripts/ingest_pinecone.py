"""ingest_pinecone.py — Chunk, embed, and upsert scraped match articles to Pinecone.

Usage:
    cd backend
    uv run python scripts/ingest_pinecone.py

Reads every .txt + .meta.json pair from backend/data/raw_texts/, splits into
overlapping chunks (1000 tokens, 200 overlap), embeds via OpenAI
text-embedding-3-small, and upserts to the Pinecone index "superliga-tactics".

Chunk IDs are deterministic: sha1(source_url + "::" + chunk_index), so re-runs
overwrite existing vectors rather than creating duplicates.

Requires env vars: OPENAI_API_KEY, PINECONE_API_KEY
"""

from __future__ import annotations

import json
import sys
from hashlib import sha1
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec

from app.config import settings

RAW_TEXTS_DIR = Path(__file__).parent.parent / "data" / "raw_texts"
INDEX_NAME = "superliga-tactics"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
CHUNK_SIZE = 1000   # tokens (cl100k_base)
CHUNK_OVERLAP = 200


def _chunk_id(source_url: str, chunk_index: int) -> str:
    return sha1(f"{source_url}::{chunk_index}".encode()).hexdigest()


def load_documents() -> list[tuple[str, dict]]:
    """Return (body_text, metadata) for every article in raw_texts/."""
    docs: list[tuple[str, dict]] = []
    for txt_path in sorted(RAW_TEXTS_DIR.glob("*.txt")):
        meta_path = txt_path.with_suffix(".meta.json")
        if not meta_path.exists():
            print(f"  ! No metadata for {txt_path.name}, skipping", file=sys.stderr)
            continue
        text = txt_path.read_text(encoding="utf-8").strip()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if text:
            docs.append((text, meta))
    return docs


def ensure_index(pc: Pinecone) -> None:
    existing = {idx.name for idx in pc.list_indexes()}
    if INDEX_NAME not in existing:
        print(f"Creating index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print("  Index created.")
    else:
        print(f"Index '{INDEX_NAME}' already exists.")


def run() -> None:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment / .env")
    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY not set in environment / .env")

    raw_docs = load_documents()
    print(f"Loaded {len(raw_docs)} articles from {RAW_TEXTS_DIR}")

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=settings.openai_api_key,
    )

    pc = Pinecone(api_key=settings.pinecone_api_key)
    ensure_index(pc)
    index = pc.Index(INDEX_NAME)
    store = PineconeVectorStore(index=index, embedding=embeddings)

    total_chunks = 0
    for text, meta in raw_docs:
        chunks = splitter.split_text(text)
        lc_docs = [
            Document(
                page_content=chunk,
                metadata={
                    "team_id": meta["team_id"],
                    "match_date": meta["match_date"],
                    "source_url": meta["source_url"],
                    "title": meta.get("title", ""),
                },
            )
            for chunk in chunks
        ]
        ids = [_chunk_id(meta["source_url"], i) for i in range(len(chunks))]
        store.add_documents(lc_docs, ids=ids)
        total_chunks += len(chunks)
        print(
            f"  Upserted {len(chunks):>2} chunks | team_id={meta['team_id']} | "
            f"{meta.get('title', '')[:60]}"
        )

    print(f"\nDone. {total_chunks} chunks upserted to '{INDEX_NAME}'.")


if __name__ == "__main__":
    run()
