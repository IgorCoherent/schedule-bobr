from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.routers import api_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Дежурства")
settings = get_settings()

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="session",
    https_only=settings.session_https_only,
    same_site="lax",
)

app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(api_router)


@app.get("/")
async def root(request: Request):
    from starlette.responses import RedirectResponse

    if request.session.get("user_id"):
        return RedirectResponse(url="/schedule", status_code=303)
    return RedirectResponse(url="/auth/login", status_code=303)
