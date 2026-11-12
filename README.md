# Дежурства (schedule-bobr)

Mobile-first веб-приложение расписания дежурств кассиров и техничек для общины храма.

## Стек

Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Jinja2, HTMX, Alpine.js (vendored).

## Локальный запуск

```bash
docker compose up -d
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run python -m app.seed.run
uv run uvicorn app.main:app --reload
```

Откройте http://127.0.0.1:8000 — логины см. `INITIAL_CREDENTIALS.md` (не коммитить).

## Тесты

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE schedule_bobr_test;"
export TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/schedule_bobr_test
export DATABASE_URL=$TEST_DATABASE_URL
export SECRET_KEY=test-secret
uv run pytest -q
```

## Деплой Render (free tier)

- Web Service **free** — сервис засыпает после простоя, первый запрос медленный.
- PostgreSQL **free** — лимит ~1 GB; политика неактивности 90 дней.
- Аватары хранятся в Postgres (bytea), **без** Persistent Disk.

См. `render.yaml` и `scripts/start.sh`.

## UI checklist (A10)

- [x] viewport meta, bottom nav «Все | Мои | Чат»
- [x] CSS variables `--color-bg`, `--font-size-base` ≥ 16px
- [x] touch targets ≥ 44px
