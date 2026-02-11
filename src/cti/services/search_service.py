import logging
from typing import Any

from elasticsearch import AsyncElasticsearch, NotFoundError

from cti.core.elasticsearch import OBSERVABLE_INDEX, OBSERVABLE_MAPPING
from cti.schemas.search import SearchHit, SearchResponse

logger = logging.getLogger(__name__)


def observable_model_to_es_doc(obs: Any) -> dict[str, Any]:
    """Convert an ORM Observable model to an Elasticsearch document dict."""
    return {
        "id": str(obs.id),
        "type": obs.type.value,
        "value": obs.value,
        "confidence_score": obs.confidence_score,
        "first_seen": obs.first_seen.isoformat() if obs.first_seen else None,
        "last_seen": obs.last_seen.isoformat() if obs.last_seen else None,
        "tlp": obs.tlp,
        "tags": [t.name for t in obs.tags] if hasattr(obs, "tags") and obs.tags else [],
        "sources": [s.name for s in obs.sources] if hasattr(obs, "sources") and obs.sources else [],
        "category": getattr(obs, "category", None),
        "created_at": obs.created_at.isoformat() if obs.created_at else None,
        "updated_at": obs.updated_at.isoformat() if obs.updated_at else None,
    }


async def ensure_index(es: AsyncElasticsearch) -> None:
    try:
        exists = await es.indices.exists(index=OBSERVABLE_INDEX)
        if not exists:
            await es.indices.create(index=OBSERVABLE_INDEX, body=OBSERVABLE_MAPPING)
            logger.info("Created Elasticsearch index: %s", OBSERVABLE_INDEX)
    except Exception:
        logger.warning("Could not create Elasticsearch index", exc_info=True)


async def index_observable(es: AsyncElasticsearch, doc: dict[str, Any]) -> None:
    await es.index(index=OBSERVABLE_INDEX, id=doc["id"], document=doc)


async def bulk_index_observables(es: AsyncElasticsearch, docs: list[dict[str, Any]]) -> None:
    if not docs:
        return
    operations: list[dict[str, Any]] = []
    for doc in docs:
        operations.append({"index": {"_index": OBSERVABLE_INDEX, "_id": doc["id"]}})
        operations.append(doc)
    await es.bulk(operations=operations, refresh="wait_for")


async def search_observables(
    es: AsyncElasticsearch,
    q: str,
    type_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    confidence_min: int | None = None,
    confidence_max: int | None = None,
    tags: list[str] | None = None,
    page: int = 1,
    size: int = 20,
) -> SearchResponse:
    must: list[dict[str, Any]] = [
        {
            "multi_match": {
                "query": q,
                "fields": ["value^3", "value.raw^5", "tags^2"],
                "type": "best_fields",
            }
        }
    ]
    filters: list[dict[str, Any]] = []

    if type_filter:
        filters.append({"term": {"type": type_filter}})
    if confidence_min is not None:
        filters.append({"range": {"confidence_score": {"gte": confidence_min}}})
    if confidence_max is not None:
        filters.append({"range": {"confidence_score": {"lte": confidence_max}}})
    if date_from or date_to:
        date_range: dict[str, str] = {}
        if date_from:
            date_range["gte"] = date_from
        if date_to:
            date_range["lte"] = date_to
        filters.append({"range": {"last_seen": date_range}})
    if tags:
        filters.append({"terms": {"tags": tags}})

    body: dict[str, Any] = {
        "query": {"bool": {"must": must, "filter": filters}},
        "highlight": {"fields": {"value": {}, "tags": {}}},
        "from": (page - 1) * size,
        "size": size,
    }

    try:
        result = await es.search(index=OBSERVABLE_INDEX, body=body)
    except NotFoundError:
        return SearchResponse(hits=[], total=0, page=page, size=size)

    hits = []
    for hit in result["hits"]["hits"]:
        source = hit["_source"]
        highlights = {}
        if "highlight" in hit:
            highlights = {k: v for k, v in hit["highlight"].items()}
        hits.append(
            SearchHit(
                id=source.get("id", hit["_id"]),
                type=source.get("type", ""),
                value=source.get("value", ""),
                confidence_score=source.get("confidence_score", 0),
                first_seen=source.get("first_seen"),
                last_seen=source.get("last_seen"),
                tlp=source.get("tlp"),
                tags=source.get("tags", []),
                score=hit["_score"],
                highlights=highlights,
            )
        )

    total_value = result["hits"]["total"]
    total = total_value["value"] if isinstance(total_value, dict) else total_value

    return SearchResponse(hits=hits, total=total, page=page, size=size)
