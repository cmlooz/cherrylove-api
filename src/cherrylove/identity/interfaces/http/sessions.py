"""How a session reaches each client (ADR-004 §1-2): web gets the refresh token only as an HttpOnly cookie,
mobile gets it in the body. The web flag is the `X-CherryLove-Client: web` header."""

from __future__ import annotations

from django.http import HttpRequest
from rest_framework.response import Response

from cherrylove.identity.application.ports import Session
from cherrylove.identity.domain.errors import ClientHeaderRequired
from cherrylove.identity.interfaces.http.serializers import TokenPairSerializer

REFRESH_COOKIE = "cl_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth/"
CLIENT_HEADER = "X-CherryLove-Client"


def is_web(request: HttpRequest) -> bool:
    return request.headers.get(CLIENT_HEADER) == "web"


def refresh_from(request: HttpRequest, body_refresh: str | None) -> str | None:
    """The web sends its refresh as a cookie and must prove it is the web app with the header (CSRF)."""
    cookie = request.COOKIES.get(REFRESH_COOKIE)
    if cookie is not None:
        if not is_web(request):
            raise ClientHeaderRequired("cookie calls need X-CherryLove-Client: web")
        return cookie
    return body_refresh


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, samesite="Strict")


def session_response(request: HttpRequest, session: Session, status: int, *, web: bool | None = None) -> Response:
    web = is_web(request) if web is None else web
    body = {"access": session.access, "access_expires_at": session.access_expires_at}
    if not web:
        body["refresh"] = session.refresh
    response = Response(TokenPairSerializer(body).data, status=status)
    if web:
        response.set_cookie(
            REFRESH_COOKIE,
            session.refresh,
            expires=session.refresh_expires_at,
            path=REFRESH_COOKIE_PATH,
            secure=True,
            httponly=True,
            samesite="Strict",
        )
    return response
