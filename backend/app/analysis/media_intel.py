from __future__ import annotations

import asyncio
import logging

from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

from app.config import settings
from app.schemas.dossier import MediaIntelligence

logger = logging.getLogger(__name__)

INDEX_NAME = "superliga-tactics"
EMBEDDING_MODEL = "text-embedding-3-small"
TOP_K = 4

# Query designed to surface tactical shape, weakness, and pattern chunks.
_QUERY = (
    "tactical weaknesses defensive shape pressing vulnerabilities "
    "build-up patterns set pieces recent form"
)

_store: PineconeVectorStore | None = None


def _get_store() -> PineconeVectorStore:
    global _store
    if _store is None:
        embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=settings.openai_api_key,
        )
        pc = Pinecone(api_key=settings.pinecone_api_key)
        index = pc.Index(INDEX_NAME)
        _store = PineconeVectorStore(index=index, embedding=embeddings)
    return _store


async def get_media_intel(team_id: int) -> MediaIntelligence:
    """Return top-K press-report chunks for *team_id* from Pinecone.

    Filters strictly by team_id so chunks from other teams are never mixed in.
    Falls back to an empty result if Pinecone is unreachable or the team has
    no scraped articles — the dossier continues without this section.
    """
    if not settings.pinecone_api_key or not settings.openai_api_key:
        return MediaIntelligence(chunks=[])
    try:
        store = _get_store()
        results = await asyncio.to_thread(
            store.similarity_search,
            _QUERY,
            k=TOP_K,
            filter={"team_id": {"$eq": team_id}},
        )
        chunks = [doc.page_content for doc in results]
    except Exception as exc:
        logger.warning("media_intel query failed team_id=%d: %s", team_id, exc)
        chunks = []
    return MediaIntelligence(chunks=chunks)
