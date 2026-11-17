"""Load and access KuralGPT document records."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DocumentStore:
    """Store and retrieve document records from a JSON file."""

    def __init__(self, data_file: Path) -> None:
        self.data_file = data_file
        self.records: list[dict[str, Any]] = []
        self.loaded = False

    def load(self) -> None:
        """Load records from the configured JSON file."""
        if not self.data_file.is_file():
            self.records = []
            self.loaded = False
            logger.warning("records file not found: %s", self.data_file)
            return

        try:
            with self.data_file.open("r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, list):
                raise ValueError("The records file must contain a JSON array.")

            if not all(isinstance(record, dict) for record in data):
                raise ValueError("Every record must be a JSON object.")

            self.records = data
            self.loaded = True

            logger.info(
                "records loaded",
                extra={"records": len(self.records)},
            )

        except (json.JSONDecodeError, ValueError) as exc:
            self.records = []
            self.loaded = False
            logger.error("records file is invalid: %s", exc)

    def list_records(self, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        """Return a paginated list of records."""
        return self.records[offset : offset + limit]

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        """Find a record using its ID."""
        for record in self.records:
            if str(record.get("id")) == record_id:
                return record
        return None

    def search_records(self, query: str) -> list[dict[str, Any]]:
        """Search records using text fields."""
        query = query.casefold().strip()

        if not query:
            return self.records.copy()

        searchable_fields = (
            "title",
            "couplet_tamil",
            "meaning_tamil",
            "meaning_english",
            "adhikaram",
            "paal",
            "theme",
        )

        return [
            record
            for record in self.records
            if any(query in str(record.get(field, "")).casefold() for field in searchable_fields)
        ]
