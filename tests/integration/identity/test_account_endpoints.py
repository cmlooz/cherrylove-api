"""Me, couple header and change password over HTTP (IMPL-API-001 F2.16; REQ-F-ACC-02/03/04, REQ-F-HOME-01)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from django.test import Client

from cherrylove.identity.infrastructure.orm import Couple, CoupleMembership, User

pytestmark = pytest.mark.integration
PASSWORD = "correct horse battery"


def _user(couple: Couple, slot: int, name: str, **fields: Any) -> User:
    user = User.objects.create_user(f"m.{uuid.uuid4().hex[:8]}@example.com", PASSWORD, name=name, **fields)
    CoupleMembership.objects.create(couple=couple, user=user, slot=slot)
    return user


def _login(client: Client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        {"email": user.email, "password": PASSWORD, "client": "mobile"},
        content_type="application/json",
    )
    pair: dict[str, str] = response.json()
    return pair


def _bearer(pair: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {pair['access']}"}


def _refresh(client: Client, pair: dict[str, str]) -> int:
    response = client.post("/api/v1/auth/refresh", {"refresh": pair["refresh"]}, content_type="application/json")
    return response.status_code


@pytest.mark.req("REQ-F-ACC-02")
@pytest.mark.django_db(transaction=True)
def test_me_shows_my_account_and_my_partner(client: Client) -> None:
    couple = Couple.objects.create()
    camila = _user(couple, 1, "Camila", birth_date=date(1996, 3, 9))
    alone = _login(client, camila)
    assert client.get("/api/v1/me", headers=_bearer(alone)).json()["partner"] is None
    andres = _user(couple, 2, "Andrés")
    me = client.get("/api/v1/me", headers=_bearer(alone)).json()
    assert me == {
        "id": str(camila.id),
        "email": camila.email,
        "name": "Camila",
        "birth_date": "1996-03-09",
        "language": "es",
        "avatar_media_id": None,
        "partner": {"id": str(andres.id), "name": "Andrés", "avatar_media_id": None},
    }
    assert "birth_date" not in client.get("/api/v1/me", headers=_bearer(_login(client, andres))).json()
    assert client.get("/api/v1/me").status_code == 401


@pytest.mark.req("REQ-F-ACC-04")
@pytest.mark.django_db(transaction=True)
def test_patch_me_edits_name_and_language_but_never_the_birth_date(client: Client) -> None:
    camila = _user(Couple.objects.create(), 1, "Camila", birth_date=date(1996, 3, 9))
    pair = _login(client, camila)
    response = client.patch(
        "/api/v1/me",
        {"name": "Cami", "language": "en", "birth_date": "2000-01-01"},
        content_type="application/json",
        headers=_bearer(pair),
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["language"], body["birth_date"]) == ("Cami", "en", "1996-03-09"), "DEC-025"
    avatar = client.patch(
        "/api/v1/me", {"avatar_media_id": str(uuid.uuid7())}, content_type="application/json", headers=_bearer(pair)
    )
    assert avatar.status_code == 400
    assert avatar.json()["errors"] == [{"pointer": "/avatar_media_id", "code": "invalid_media"}]


@pytest.mark.req("REQ-F-ACC-03")
@pytest.mark.django_db(transaction=True)
def test_changing_the_password_keeps_this_device_and_signs_out_the_others(client: Client) -> None:
    camila = _user(Couple.objects.create(), 1, "Camila")
    this_device, other_device = _login(client, camila), _login(client, camila)
    wrong = client.post(
        "/api/v1/me/password",
        {"current_password": "not it", "new_password": "a new long passphrase"},
        content_type="application/json",
        headers=_bearer(this_device),
    )
    assert wrong.status_code == 400
    assert wrong.json()["errors"] == [{"pointer": "/current_password", "code": "incorrect_password"}]

    changed = client.post(
        "/api/v1/me/password",
        {"current_password": PASSWORD, "new_password": "a new long passphrase"},
        content_type="application/json",
        headers=_bearer(this_device),
    )
    assert changed.status_code == 204
    assert _refresh(client, other_device) == 401
    assert _refresh(client, this_device) == 200, "the current session survives (DEC-051)"
    camila.refresh_from_db()
    assert camila.check_password("a new long passphrase")


@pytest.mark.req("REQ-F-HOME-01")
@pytest.mark.django_db(transaction=True)
def test_the_couple_header_lists_both_partners_in_slot_order(client: Client) -> None:
    couple = Couple.objects.create(relationship_start=date(2023, 2, 14))
    camila, andres = _user(couple, 1, "Camila"), _user(couple, 2, "Andrés")
    header = client.get("/api/v1/couple", headers=_bearer(_login(client, andres))).json()
    assert [partner["id"] for partner in header["partners"]] == [str(camila.id), str(andres.id)]
    assert (header["id"], header["relationship_start"], header["timezone"]) == (
        str(couple.id),
        "2023-02-14",
        "America/Bogota",
    )
    assert isinstance(header["days_together"], int)
    assert header["days_together"] > 1000
