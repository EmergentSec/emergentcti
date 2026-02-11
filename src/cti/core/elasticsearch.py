from elasticsearch import AsyncElasticsearch

from cti.core.config import get_settings

OBSERVABLE_INDEX = "cti-observables"

OBSERVABLE_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "type": {"type": "keyword"},
            "value": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "confidence_score": {"type": "integer"},
            "first_seen": {"type": "date"},
            "last_seen": {"type": "date"},
            "tlp": {"type": "keyword"},
            "context": {"type": "object", "enabled": False},
            "tags": {"type": "keyword"},
            "sources": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
}


def get_es_client() -> AsyncElasticsearch:
    settings = get_settings()
    return AsyncElasticsearch(settings.ELASTICSEARCH_URL)
