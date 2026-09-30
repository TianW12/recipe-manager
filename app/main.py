"""Application entry point — wiring only.

This file no longer contains any page logic. Its single job is to assemble the
app: load configuration, create the FastAPI instance, add middleware, mount the
static files, and plug in the route modules. The actual work lives in:

    app/routes/       -> the URL handlers (recipes, auth, pwa)
    app/repository.py -> every SQL query (data access layer)
    app/db.py         -> database connection + schema
    app/templating.py -> the shared Jinja2 engine

Run it with:  uvicorn app.main:app --reload
``app.main:app`` means "the object called ``app`` inside app/main.py".
"""

from dotenv import load_dotenv

# Load .env before anything reads os.environ (SECRET_KEY, SMTP_*, ...).
# Real environment variables still take precedence over the file.
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .db import init_db
from .security import get_secret_key
from .templating import BASE
from .routes import auth, pwa, recipes

# Ensure the database and its tables exist before we serve any request.
init_db()

app = FastAPI(title="Recipes")

# Signs the session cookie so "logged in" state cannot be forged by the client.
app.add_middleware(
    SessionMiddleware,
    secret_key=get_secret_key(),
    same_site="lax",  # blocks cross-site POSTs (basic CSRF protection)
    max_age=60 * 60 * 24 * 30,  # stay logged in for 30 days
)

# Serve CSS/JS/icons directly from disk at URLs beginning with /static/.
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

# Plug in the route modules. Each is a thin APIRouter defined under app/routes/.
app.include_router(recipes.router)
app.include_router(auth.router)
app.include_router(pwa.router)
