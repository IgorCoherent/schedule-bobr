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

Как у [rct_final](https://github.com/IgorKheidorov/rct_final): подключить GitHub и Blueprint.

1. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
2. Подключить репозиторий **https://github.com/IgorCoherent/schedule-bobr** (ветка `main`)
3. Применить `render.yaml` (web `schedule-bobr` + Postgres `schedule-bobr-db`)
4. Дождаться деплоя; проверить `/health` → `{"status":"ok"}`
5. Вход: `tamara` / `Tamara2025!` (см. `INITIAL_CREDENTIALS.md` локально, не в git)

- Web Service **free** — засыпает после простоя.
- PostgreSQL **free** — аватары в БД (bytea), без Persistent Disk.
- `SEED_ON_START=true` создаёт учётки при первом старте.

См. `render.yaml` и `scripts/start.sh`.

## UI checklist (A10)

- [x] viewport meta, bottom nav «Все | Мои | Чат»
- [x] CSS variables `--color-bg`, `--font-size-base` ≥ 16px
- [x] touch targets ≥ 44px
