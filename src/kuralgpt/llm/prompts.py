"""Load and list versioned prompt files."""

import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def list_prompt_versions(
    task: str,
    prompts_dir: Path | None = None,
) -> list[Path]:
    """Find prompt files and return them in numeric version order."""
    directory = prompts_dir or PROMPTS_DIR
    pattern = re.compile(rf"^{re.escape(task)}_v(\d+)\.md$")

    matches = []

    if not directory.exists():
        return matches

    for path in directory.glob(f"{task}_v*.md"):
        match = pattern.match(path.name)
        if match:
            matches.append((int(match.group(1)), path))

    return [path for _, path in sorted(matches, key=lambda item: item[0])]


def load_prompt(
    task: str,
    version: int,
    prompts_dir: Path | None = None,
) -> str:
    """Load one specific prompt version."""
    directory = prompts_dir or PROMPTS_DIR
    path = directory / f"{task}_v{version}.md"

    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")

    return path.read_text(encoding="utf-8")
