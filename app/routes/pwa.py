"""PWA plumbing: manifest + service worker.

These two files must be served from the site root (not /static/) so the
service worker can control the whole app and the browser can find the
manifest, each with its correct Content-Type header.
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..templating import BASE

router = APIRouter()


@router.get("/manifest.webmanifest")
def manifest():
    """The PWA manifest that makes the app installable on a phone."""
    return FileResponse(
        BASE / "static" / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@router.get("/sw.js")
def service_worker():
    """Service worker served at the root so its cache scope covers the app."""
    return FileResponse(
        BASE / "static" / "js" / "sw.js", media_type="application/javascript"
    )
