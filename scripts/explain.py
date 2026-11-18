import asyncio
import json

from sqlalchemy import text

from kuralgpt.db.session import get_engine


async def main():
    engine = get_engine()

    async with engine.connect() as connection:
        print("\n1. Normal query plan:")
        result = await connection.execute(
            text("""
                EXPLAIN ANALYZE
                SELECT id, external_id
                FROM documents
                WHERE metadata @> CAST(:filter AS jsonb)
            """),
            {"filter": json.dumps({"kural_no": 1})},
        )

        for row in result:
            print(row[0])

        print("\n2. Query plan with sequential scans disabled:")
        await connection.execute(text("SET enable_seqscan = off"))

        result = await connection.execute(
            text("""
                EXPLAIN ANALYZE
                SELECT id, external_id
                FROM documents
                WHERE metadata @> CAST(:filter AS jsonb)
            """),
            {"filter": json.dumps({"kural_no": 1})},
        )

        for row in result:
            print(row[0])

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
