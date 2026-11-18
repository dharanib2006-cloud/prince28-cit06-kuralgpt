"""Statistics endpoint for KuralGPT."""

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kuralgpt.api.deps import get_db_session
from kuralgpt.models import Document

router = APIRouter(prefix="/v1/stats", tags=["statistics"])


@router.get("")
def get_statistics(
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Return total records and counts grouped by paal from PostgreSQL."""

    total_records = session.scalar(select(func.count()).select_from(Document)) or 0

    paal_statement = select(Document.document_metadata["paal"].as_string())

    paal_values = session.scalars(paal_statement).all()

    counts_by_paal = dict(Counter(value for value in paal_values if value is not None))

    return {
        "total_records": total_records,
        "counts_by_paal": counts_by_paal,
    }
