"""Statistics endpoint for KuralGPT."""

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends

from kuralgpt.api.deps import get_document_store
from kuralgpt.store import DocumentStore

router = APIRouter(prefix="/v1/stats", tags=["statistics"])


@router.get("")
def get_statistics(
    store: DocumentStore = Depends(get_document_store),
) -> dict[str, Any]:
    """Return total records and counts grouped by paal."""

    counts = Counter(record.get("paal", "Unknown") for record in store.records)

    return {
        "total_records": len(store.records),
        "counts_by_paal": dict(counts),
    }
