"""Generate an ingestion report from the KuralGPT database."""

from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from kuralgpt.database import get_session_factory
from kuralgpt.models import Document, IngestItem, LlmCall, Page

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "INGEST_REPORT.md"

START = "<!-- generated:start -->"
END = "<!-- generated:end -->"

SOURCE_TYPES = ("html", "json", "markdown", "text")


def collect_metrics() -> dict:
    """Collect source-document, page, failure and LLM usage metrics."""
    session_factory = get_session_factory()

    with session_factory() as session:
        documents = (
            session.scalar(
                select(func.count(Document.id)).where(Document.doc_type.in_(SOURCE_TYPES))
            )
            or 0
        )

        pages = (
            session.scalar(
                select(func.count(Page.id))
                .join(Document, Page.document_id == Document.id)
                .where(Document.doc_type.in_(SOURCE_TYPES))
            )
            or 0
        )

        later = aliased(IngestItem)

        later_attempt_exists = (
            select(later.id)
            .where(
                later.record["path"].as_string() == IngestItem.record["path"].as_string(),
                later.id > IngestItem.id,
            )
            .exists()
        )

        dead_letter = (
            session.scalar(
                select(func.count(IngestItem.id)).where(
                    IngestItem.status == "failed",
                    IngestItem.record["path"].as_string().is_not(None),
                    ~later_attempt_exists,
                )
            )
            or 0
        )

        extraction_calls = (
            session.scalar(select(func.count(LlmCall.id)).where(LlmCall.purpose == "extract")) or 0
        )

        input_tokens = (
            session.scalar(
                select(func.coalesce(func.sum(LlmCall.tokens_in), 0)).where(
                    LlmCall.purpose == "extract"
                )
            )
            or 0
        )

        output_tokens = (
            session.scalar(
                select(func.coalesce(func.sum(LlmCall.tokens_out), 0)).where(
                    LlmCall.purpose == "extract"
                )
            )
            or 0
        )

    return {
        "documents": documents,
        "pages": pages,
        "dead_letter": dead_letter,
        "extraction_calls": extraction_calls,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
    }


def generated_content(metrics: dict) -> str:
    """Build the automatically generated report section."""
    total_tokens = metrics["input_tokens"] + metrics["output_tokens"]
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    return "\n".join(
        [
            "## Generated Ingestion Measurements",
            "",
            f"- Report generated: **{generated_at}**",
            f"- Source documents: **{metrics['documents']:,}**",
            f"- Parsed pages: **{metrics['pages']:,}**",
            f"- Unresolved latest failed sources: **{metrics['dead_letter']:,}**",
            f"- Recorded extraction calls: **{metrics['extraction_calls']:,}**",
            f"- Recorded extraction input tokens: **{metrics['input_tokens']:,}**",
            f"- Recorded extraction output tokens: **{metrics['output_tokens']:,}**",
            f"- Total recorded extraction tokens: **{total_tokens:,}**",
            "",
            "### Token measurement note",
            "",
            "Token counts are summed from recorded LLM extraction calls in "
            "the database. They include repeated calls and retries, so they "
            "measure provider usage rather than the unique token size of the "
            "corpus. Compare them with the planning estimate in "
            "`docs/CAPACITY.md` with this difference in scope in mind.",
            "",
        ]
    )


def update_report(content: str) -> None:
    """Update generated markers while preserving the learning notes."""
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    if REPORT.exists():
        existing = REPORT.read_text(encoding="utf-8")

        if START in existing and END in existing:
            before, remainder = existing.split(START, 1)
            _, after = remainder.split(END, 1)
            updated = f"{before}{START}\n{content}\n{END}{after}"
        else:
            updated = f"{existing.rstrip()}\n\n{START}\n{content}\n{END}\n"
    else:
        updated = f"""# KuralGPT Ingestion Report

{START}
{content}
{END}

## What I learnt

- I learned how the API queues ingestion jobs for background worker processing.
- I learned that a restarted worker can recover interrupted jobs after their locks expire.
- I learned to verify ingestion through database statuses and unique document IDs.

"""

    REPORT.write_text(updated, encoding="utf-8")


def main() -> None:
    metrics = collect_metrics()
    update_report(generated_content(metrics))

    total_tokens = metrics["input_tokens"] + metrics["output_tokens"]

    print(
        f"documents={metrics['documents']} "
        f"pages={metrics['pages']} "
        f"dead_letter={metrics['dead_letter']} "
        f"extraction_tokens={total_tokens} "
        "-> docs/INGEST_REPORT.md"
    )


if __name__ == "__main__":
    main()
