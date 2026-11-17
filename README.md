
# KuralGPT

A Thirukkural companion for teachers that helps find the right Kural for a value, situation, or classroom lesson.

**Status:** Day 1 foundation - Python package and project setup completed. FastAPI service and quality checks are under development. Live URL will be added later.

## Who it's for

Tamil teachers at government schools in Chennai who prepare daily value-education lessons from Thirukkural for students in classes 6-10.

## The problem

Teachers need to select suitable Thirukkural couplets while preparing value-education lessons for their students. Finding the correct couplet among 1,330 Kurals and understanding its meaning can take time. General-purpose chatbots may sometimes provide incorrect couplets or meanings, which can create confusion when teaching classical Tamil literature. KuralGPT aims to make this process easier by helping teachers find relevant, authentic Kurals with clear explanations.

## Data sources

Thirukkural contains 1,330 couplets along with commentaries and English translations.

- https://github.com/tk120404/thirukkural
- https://www.projectmadurai.org/

**Terms:** The tk120404 dataset is licensed under Apache-2.0. Project Madurai texts are available for non-commercial use with credit.

## Hardest problem (my interview story)

The hardest technical challenge is retrieving the correct Kural for a teacher's question. Classical Tamil has unique vocabulary and word forms, so tokenising and creating useful embeddings for classical Tamil can be challenging. The system must retrieve the correct couplet instead of generating or inventing a similar-looking one.

## Signature feature

**Kural card:** Each result will show:

- Kural number
- Original Tamil couplet
- Simple Tamil meaning
- English meaning
- Related value or theme

## Target metric

- Zero invented or misquoted Kurals in 100 evaluated answers.
- Correct Kural should appear in the top 3 results for at least 85% of 50 theme-based questions.

## Run it locally

```bash
uv sync
```

On Windows, create your environment file:

```powershell
copy .env.example .env
```

Start the application:

```bash
uv run uvicorn kuralgpt.api.main:create_app --factory --reload
```

Then open:

http://localhost:8000/docs

## Checks

Run the tests:

```bash
uv run pytest
```

Run the code quality check:

```bash
uv run ruff check .
```
