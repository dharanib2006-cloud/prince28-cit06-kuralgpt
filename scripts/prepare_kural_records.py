"""Prepare all 1,330 Thirukkural records for database loading."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_FILE = PROJECT_ROOT / "data" / "kural_records.json"


def find_file(pattern: str) -> Path:
    """Find exactly one source file matching a pattern."""
    matches = list(RAW_DIR.rglob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one file matching {pattern}, found {len(matches)}")
    return matches[0]


def main() -> None:
    main_file = find_file("*thirukkural-03688010.json")
    detail_file = find_file("*detail-9c7ff7d8.json")

    source = json.loads(main_file.read_text(encoding="utf-8"))
    detail = json.loads(detail_file.read_text(encoding="utf-8"))

    kurals = source["kural"]
    chapters = {}

    # Build the Kural number -> paal and adhikaram mapping.
    for paal in detail[0]["section"]["detail"]:
        for group in paal["chapterGroup"]["detail"]:
            for chapter in group["chapters"]["detail"]:
                for number in range(chapter["start"], chapter["end"] + 1):
                    if number in chapters:
                        raise ValueError(f"Duplicate chapter mapping: Kural {number}")

                    chapters[number] = {
                        "paal": paal["name"],
                        "adhikaram": chapter["name"],
                    }

    records = []

    for kural in kurals:
        number = int(kural["Number"])

        if number not in chapters:
            raise ValueError(f"No chapter mapping for Kural {number}")

        records.append(
            {
                "id": f"{number:03d}",
                "kural_no": number,
                "paal": chapters[number]["paal"],
                "adhikaram": chapters[number]["adhikaram"],
                "couplet_tamil": (f"{kural['Line1']}\n{kural['Line2']}"),
                "meaning_tamil": None,
                "commentary_tamil": kural["mv"],
                "meaning_english": kural["Translation"],
                "theme": None,
                # Preserve the other source fields too.
                "commentary_mv": kural["mv"],
                "commentary_sp": kural["sp"],
                "commentary_mk": kural["mk"],
                "explanation_english": kural["explanation"],
                "couplet_english": kural["couplet"],
                "transliteration1": kural["transliteration1"],
                "transliteration2": kural["transliteration2"],
            }
        )

    records.sort(key=lambda record: record["kural_no"])

    expected_numbers = list(range(1, 1331))
    actual_numbers = [record["kural_no"] for record in records]

    if actual_numbers != expected_numbers:
        raise ValueError("Kural numbers are missing, duplicated, or out of order")

    if len(chapters) != 1330:
        raise ValueError(f"Expected 1330 chapter mappings, found {len(chapters)}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Dataset preparation completed!")
    print(f"Total records: {len(records)}")
    print(f"Chapter mappings: {len(chapters)}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
