"""Application assembly: wires routes together and exposes create_app()."""

from __future__ import annotations

from datetime import datetime

from . import auth, db
from .config import settings
from .routes import admin, public
from .web import Application, Request, Response, html_response, render


def _error_page(request: Request, status: int, message: str) -> Response:
    titles = {
        404: "Page not found",
        405: "Method not allowed",
        500: "Something went wrong",
    }
    return html_response(
        render(
            "error.html",
            brand_name=settings.brand_name,
            status=status,
            title=titles.get(status, "Error"),
            message=message,
            year=datetime.now().year,
        ),
        status=status,
    )


def create_app() -> Application:
    app = Application()
    public.register(app.router)
    admin.register(app.router)
    app.error_page = _error_page

    # Touch the database so the schema exists before the first request, and
    # make sure somebody can actually log in to the dashboard.
    db.get_connection()
    created, message = auth.ensure_bootstrap_admin()
    if created:
        print(f"[setup] {message}")
        if settings.admin_password == "ChangeMe123!":
            print(
                "[setup] WARNING: using the default admin password. "
                "Set ADMIN_PASSWORD in .env and run `python3 run.py set-password`."
            )
    if settings.secret_key == "dev-only-insecure-secret-change-me" and not settings.debug:
        print("[setup] WARNING: SECRET_KEY is still the development default.")

    return app
