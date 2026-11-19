
# KuralGPT

A Thirukkural companion for teachers that helps find the right Kural for a value, situation, or classroom lesson.

**Status:** Day 4 build completed - containerized API, Docker Compose stack, database migrations, unit and integration tests, and development task runner.

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

## Run locally in one command

You need Docker Desktop running. From a fresh clone:

```bash
docker compose up --build
```

The API is available at:
- API documentation: http://localhost:8000/docs
- Liveness check: http://localhost:8000/health
- Readiness check: http://localhost:8000/ready

Press Ctrl+C to stop the application. Then run:
```bash
docker compose down
```

Use `docker compose down -v` only when you also want to delete the database volumes.

### Develop and test

| Task | Command |
|---|---|
| Start development server | `uv run poe dev` |
| Run unit tests | `uv run poe test` |
| Run integration tests | `uv run poe test-integration` |
| Run coverage | `uv run poe cov` |
| Run lint and format checks | `uv run poe lint` |
