"""Site settings (admin), passwordless sign-in, session-based editing,
edit-link emails and the scope of CORS."""

import json
import re

import pytest
from fastapi.testclient import TestClient

import app.mail as mail
from app.api.auth import login_limit
from app.main import app
from app.mail import MailError
from app.settings import settings
from conftest import write_fallback

SMTP = {"smtp_host": "smtp.example.org", "mail_from": "IMPULSE Curator <curator@example.org>"}


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(mail, "_send_sync", lambda site, msg: sent.append(msg))
    login_limit.reset()
    return sent


@pytest.fixture
def client(config_dir, outbox):
    write_fallback(config_dir, "demo")
    with TestClient(app) as c:
        yield c


def _text(msg) -> str:
    return msg.get_body(("plain",)).get_content()


def _link(msg, fragment: str) -> str:
    return re.search(rf"#{fragment}=([\w-]+)", _text(msg)).group(1)


def _create(client, email=None):
    body = {"name": "Mine", "items": [{"source": "demo", "asset_id": "demo"}]}
    if email:
        body["email"] = email
    data = client.post("/api/collections", json=body).json()
    return data["collection"]["id"], data["edit_key"]


def _sign_in(client, outbox, email):
    client.post("/api/auth/login", json={"email": email})
    token = _link(outbox[-1], "token")
    return client.post("/api/auth/verify", json={"token": token})


# ---- settings ----

def test_config_reflects_admin_settings(client):
    assert client.get("/api/config").json() == {
        "app_name": "IMPULSE Curator",
        "submission_email": None,
        "sign_in_available": False,
        "max_assets_per_collection": settings.max_assets_per_collection,
    }
    client.put("/admin/api/settings", json={**SMTP, "submission_email": "team@euimpulse.eu"})

    config = client.get("/api/config").json()
    assert (config["submission_email"], config["sign_in_available"]) == ("team@euimpulse.eu", True)


def test_smtp_password_is_write_only(client, monkeypatch):
    saved = client.put("/admin/api/settings", json={"smtp_password": "s3cret"}).json()
    assert "smtp_password" not in saved
    assert saved["smtp_password_set"] is True
    assert "s3cret" not in json.dumps(client.get("/admin/api/settings").json())

    cleared = client.put("/admin/api/settings", json={"smtp_password": ""}).json()
    assert cleared["smtp_password_set"] is False

    monkeypatch.setattr(settings, "smtp_password", "from-env")
    assert client.get("/admin/api/settings").json()["smtp_password_from_env"] is True


def test_invalid_settings_are_rejected_and_not_saved(client):
    r = client.put("/admin/api/settings", json={"smtp_port": 0, "smtp_host": "x"})
    assert r.status_code == 422
    assert client.get("/admin/api/settings").json()["smtp_host"] == ""


def test_test_email(client, outbox, monkeypatch):
    client.put("/admin/api/settings", json=SMTP)
    assert client.post("/admin/api/settings/test-email", json={"to": "me@example.org"}).status_code == 200
    assert outbox[-1]["To"] == "me@example.org"

    def broken(site, msg):
        raise MailError("The SMTP server rejected the username or password")

    monkeypatch.setattr(mail, "_send_sync", broken)
    r = client.post("/admin/api/settings/test-email", json={"to": "me@example.org"})
    assert (r.status_code, r.json()["detail"]) == (502, "The SMTP server rejected the username or password")


# ---- sign-in ----

def test_sign_in_is_unavailable_without_email_setup(client):
    assert client.post("/api/auth/login", json={"email": "me@example.org"}).status_code == 503


def test_sign_in_link_only_goes_to_addresses_with_collections(client, outbox):
    client.put("/admin/api/settings", json=SMTP)
    _create(client, email="Me@Example.org")

    stranger = client.post("/api/auth/login", json={"email": "stranger@example.org"})
    owner = client.post("/api/auth/login", json={"email": "me@example.org"})

    assert stranger.status_code == owner.status_code == 202
    assert stranger.json() == owner.json()  # no hint whether the address is known
    assert [m["To"] for m in outbox] == ["me@example.org"]
    assert "http://bridge.test/signin#token=" in _text(outbox[0])


def test_session_lists_and_edits_own_collections(client, outbox):
    client.put("/admin/api/settings", json=SMTP)
    cid, _ = _create(client, email="me@example.org")
    _create(client, email="other@example.org")

    verified = _sign_in(client, outbox, "me@example.org")

    assert verified.json() == {"email": "me@example.org"}
    assert client.get("/api/auth/me").json() == {"email": "me@example.org"}
    assert [c["id"] for c in client.get("/api/me/collections").json()["collections"]] == [cid]
    assert client.get(f"/api/collections/{cid}").json()["can_edit"] is True
    assert client.patch(f"/api/collections/{cid}", json={"name": "Renamed"}).status_code == 200


def test_session_writes_from_other_sites_are_refused(client, outbox):
    client.put("/admin/api/settings", json=SMTP)
    cid, _ = _create(client, email="me@example.org")
    _sign_in(client, outbox, "me@example.org")

    evil = client.patch(f"/api/collections/{cid}", json={"name": "x"}, headers={"Origin": "https://evil.example"})
    own = client.patch(f"/api/collections/{cid}", json={"name": "x"}, headers={"Origin": "http://bridge.test"})

    assert (evil.status_code, evil.json()["detail"]) == (403, "Cross-site request refused")
    assert own.status_code == 200


def test_session_does_not_grant_other_peoples_collections(client, outbox):
    client.put("/admin/api/settings", json=SMTP)
    _create(client, email="me@example.org")
    theirs, _ = _create(client, email="other@example.org")
    _sign_in(client, outbox, "me@example.org")

    assert client.patch(f"/api/collections/{theirs}", json={"name": "x"}).status_code == 403
    assert client.get(f"/api/collections/{theirs}").json()["can_edit"] is False


def test_sign_in_links_work_once_and_expire(client, outbox):
    client.put("/admin/api/settings", json=SMTP)
    _create(client, email="me@example.org")
    client.post("/api/auth/login", json={"email": "me@example.org"})
    token = _link(outbox[-1], "token")

    assert client.post("/api/auth/verify", json={"token": token}).status_code == 200
    assert client.post("/api/auth/verify", json={"token": token}).status_code == 400

    client.post("/api/auth/login", json={"email": "me@example.org"})
    expired = _link(outbox[-1], "token")
    from app.storage import get_auth_store

    with get_auth_store().db.transaction() as conn:
        conn.execute("UPDATE login_tokens SET expires_at = '2000-01-01T00:00:00Z'")
    assert client.post("/api/auth/verify", json={"token": expired}).status_code == 400


def test_logout(client, outbox):
    client.put("/admin/api/settings", json=SMTP)
    _create(client, email="me@example.org")
    _sign_in(client, outbox, "me@example.org")

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").json() == {"email": None}
    assert client.get("/api/me/collections").status_code == 401


def test_links_per_address_are_limited(client, outbox):
    client.put("/admin/api/settings", json=SMTP)
    _create(client, email="me@example.org")
    for _ in range(7):
        client.post("/api/auth/login", json={"email": "me@example.org"})
    assert len(outbox) == 5


# ---- edit link by email ----

def test_email_edit_link(client, outbox):
    client.put("/admin/api/settings", json=SMTP)
    cid, key = _create(client, email="me@example.org")
    headers = {"Authorization": f"Bearer {key}"}

    r = client.post(f"/api/collections/{cid}/email-link", headers=headers)

    assert (r.status_code, r.json()) == (202, {"sent_to": "me@example.org"})
    assert f"http://bridge.test/c/{cid}/edit#key={key}" in _text(outbox[-1])


def test_email_edit_link_needs_an_address(client):
    client.put("/admin/api/settings", json=SMTP)
    cid, key = _create(client)
    r = client.post(f"/api/collections/{cid}/email-link", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 422


# ---- CORS ----

def test_cors_covers_the_impulse_api_but_not_the_web_app_api(client):
    origin = {"Origin": "https://impulse-frontend.example"}
    impulse = client.get("/health", headers=origin)
    web = client.get("/api/sources", headers=origin)
    preflight = client.options(
        "/api/collections",
        headers={**origin, "Access-Control-Request-Method": "POST"},
    )

    assert impulse.headers["access-control-allow-origin"] == "https://impulse-frontend.example"
    assert "access-control-allow-origin" not in web.headers
    assert "access-control-allow-origin" not in preflight.headers


# ---- message building and log-only delivery (no SMTP server needed) ----

def test_messages_escape_html_and_log_only_mode_logs(monkeypatch, caplog):
    from app.site_settings import SiteSettings

    site = SiteSettings(**SMTP)
    msg = mail.build_message(site, "me@example.org", "Hi", ["<b>Masters</b> & co"], link=("Open", "https://x.test/?a=1&b=2"))
    html_part = msg.get_body(("html",)).get_content()
    assert "&lt;b&gt;Masters&lt;/b&gt; &amp; co" in html_part
    assert 'href="https://x.test/?a=1&amp;b=2"' in html_part
    assert "https://x.test/?a=1&b=2" in _text(msg)

    monkeypatch.setattr(settings, "mail_log_only", True)
    with caplog.at_level("WARNING", logger="app.mail"):
        mail._send_sync(SiteSettings(), msg)  # no SMTP configured: logged, not sent
    assert "Mail (log only) to me@example.org" in caplog.text
