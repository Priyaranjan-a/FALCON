from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import OWNER, SETUP, WRITE, invite_and_activate


def test_setup_status_before_and_after(client: TestClient) -> None:
    status = client.get("/api/v1/setup").json()
    assert status["initialised"] is False
    assert "moderate" in status["horizon"]["scenarios"]

    response = client.post("/api/v1/setup", json=SETUP)
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["role"] == "owner"
    assert "org.manage" in body["permissions"]
    assert body["organisation"]["name"] == "National Test Agency"

    status = client.get("/api/v1/setup").json()
    assert status == {"initialised": True, "version": status["version"], "desktop": False}


def test_setup_runs_only_once(owner: TestClient) -> None:
    again = owner.post("/api/v1/setup", json=SETUP)
    assert again.status_code == 409
    assert again.json()["code"] == "already_initialised"


def test_setup_rejects_weak_password(client: TestClient) -> None:
    weak = {**SETUP, "owner": {**OWNER, "password": "short"}}
    response = client.post("/api/v1/setup", json=weak)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "weak_password"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert client.get("/api/v1/setup").json()["initialised"] is False


def test_session_cookie_is_hardened(client: TestClient) -> None:
    response = client.post("/api/v1/setup", json=SETUP)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/" in cookie


def test_sign_out_and_sign_in(owner: TestClient) -> None:
    assert owner.post("/api/v1/auth/sign-out", headers=WRITE).status_code == 204
    assert owner.get("/api/v1/auth/me").status_code == 401

    bad = owner.post("/api/v1/auth/sign-in", json={"email": OWNER["email"], "password": "wrong-password"})
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_credentials"

    good = owner.post("/api/v1/auth/sign-in", json={"email": OWNER["email"].upper(), "password": OWNER["password"]})
    assert good.status_code == 200
    assert owner.get("/api/v1/auth/me").json()["user"]["email"] == OWNER["email"]


def test_unknown_account_gets_the_same_error(owner: TestClient) -> None:
    response = owner.post("/api/v1/auth/sign-in", json={"email": "nobody@falcon.test", "password": "whatever-123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "The email or password is incorrect."


def test_account_locks_after_repeated_failures(owner: TestClient) -> None:
    for _ in range(5):
        assert owner.post("/api/v1/auth/sign-in", json={"email": OWNER["email"], "password": "nope-nope"}).status_code == 401
    locked = owner.post("/api/v1/auth/sign-in", json={"email": OWNER["email"], "password": OWNER["password"]})
    assert locked.status_code == 423
    assert locked.json()["code"] == "account_locked"


def test_state_change_without_request_header_is_rejected(owner: TestClient) -> None:
    response = owner.patch("/api/v1/auth/me", json={"name": "Someone Else"})
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_rejected"
    assert owner.patch("/api/v1/auth/me", json={"name": "Asha R. Raman"}, headers=WRITE).status_code == 200


def test_password_change_revokes_other_sessions(owner: TestClient) -> None:
    other = TestClient(owner.app)
    assert other.post("/api/v1/auth/sign-in", json={"email": OWNER["email"], "password": OWNER["password"]}).status_code == 200
    assert len(owner.get("/api/v1/auth/sessions").json()) == 2

    reused = owner.post("/api/v1/auth/password", json={"current_password": OWNER["password"], "new_password": OWNER["password"]}, headers=WRITE)
    assert reused.json()["code"] == "password_reused"

    changed = owner.post(
        "/api/v1/auth/password",
        json={"current_password": OWNER["password"], "new_password": "Kyber-Dilithium-2024"},
        headers=WRITE,
    )
    assert changed.status_code == 204
    assert other.get("/api/v1/auth/me").status_code == 401
    assert owner.get("/api/v1/auth/me").status_code == 200


def test_sign_out_other_devices(owner: TestClient) -> None:
    other = TestClient(owner.app)
    other.post("/api/v1/auth/sign-in", json={"email": OWNER["email"], "password": OWNER["password"]})
    result = owner.request("DELETE", "/api/v1/auth/sessions", headers=WRITE).json()
    assert result == {"revoked": 1}
    assert other.get("/api/v1/auth/me").status_code == 401


def test_invitation_flow_and_role_enforcement(owner: TestClient) -> None:
    viewer = invite_and_activate(owner, "viewer@falcon.test", "viewer")
    me = viewer.get("/api/v1/auth/me").json()
    assert me["user"]["role"] == "viewer"
    assert me["permissions"] == ["inventory.read", "systems.read"]
    assert viewer.get("/api/v1/systems").status_code == 200
    denied = viewer.post("/api/v1/systems", json={}, headers=WRITE)
    assert denied.status_code == 403
    assert viewer.get("/api/v1/audit").status_code == 403


def test_invitation_link_is_single_use(owner: TestClient) -> None:
    response = owner.post("/api/v1/members", json={"email": "a@falcon.test", "name": "Arun Mehta", "role": "analyst"}, headers=WRITE)
    secret = response.json()["activation_link"].split("#", 1)[1]
    preview = owner.get(f"/api/v1/auth/invitations/{secret}").json()
    assert preview["email"] == "a@falcon.test"
    assert preview["organisation"] == "National Test Agency"
    first = TestClient(owner.app).post("/api/v1/auth/activate", json={"token": secret, "name": "Arun Mehta", "password": "Sphincs-Plus-2031"})
    assert first.status_code == 200
    second = TestClient(owner.app).post("/api/v1/auth/activate", json={"token": secret, "name": "Arun Mehta", "password": "Sphincs-Plus-2031"})
    assert second.status_code == 404


def test_duplicate_invitation_conflicts(owner: TestClient) -> None:
    owner.post("/api/v1/members", json={"email": "b@falcon.test", "name": "Bina Shah", "role": "analyst"}, headers=WRITE)
    again = owner.post("/api/v1/members", json={"email": "B@falcon.test", "name": "Bina Shah", "role": "analyst"}, headers=WRITE)
    assert again.status_code == 409


def test_suspending_a_member_ends_their_sessions(owner: TestClient) -> None:
    analyst = invite_and_activate(owner, "analyst@falcon.test", "analyst")
    member_id = analyst.get("/api/v1/auth/me").json()["user"]["id"]
    response = owner.patch(f"/api/v1/members/{member_id}", json={"status": "disabled"}, headers=WRITE)
    assert response.status_code == 200
    assert analyst.get("/api/v1/auth/me").status_code == 401


def test_owner_is_protected(owner: TestClient) -> None:
    owner_id = owner.get("/api/v1/auth/me").json()["user"]["id"]
    admin = invite_and_activate(owner, "admin@falcon.test", "admin")
    assert admin.patch(f"/api/v1/members/{owner_id}", json={"role": "viewer"}, headers=WRITE).status_code == 403
    assert admin.delete(f"/api/v1/members/{owner_id}", headers=WRITE).status_code == 403
    assert owner.delete(f"/api/v1/members/{owner_id}", headers=WRITE).status_code == 403


def test_access_tokens(owner: TestClient) -> None:
    created = owner.post("/api/v1/tokens", json={"name": "CI pipeline", "expires_in_days": 30}, headers=WRITE)
    assert created.status_code == 201
    secret = created.json()["secret"]
    assert secret.startswith("flc_")

    bearer = TestClient(owner.app, headers={"Authorization": f"Bearer {secret}"})
    assert bearer.get("/api/v1/systems").status_code == 200
    # Tokens cannot mint tokens or manage sessions.
    assert bearer.post("/api/v1/tokens", json={"name": "nested"}).status_code == 403
    assert bearer.get("/api/v1/auth/sessions").status_code == 403

    token_id = created.json()["token"]["id"]
    assert owner.delete(f"/api/v1/tokens/{token_id}", headers=WRITE).status_code == 204
    assert bearer.get("/api/v1/systems").status_code == 401
    assert TestClient(owner.app, headers={"Authorization": "Bearer flc_not-a-real-token"}).get("/api/v1/systems").status_code == 401


def test_access_reset_issues_a_new_link(owner: TestClient) -> None:
    member = invite_and_activate(owner, "reset@falcon.test", "analyst")
    member_id = member.get("/api/v1/auth/me").json()["user"]["id"]
    response = owner.post(f"/api/v1/members/{member_id}/invitation", headers=WRITE)
    assert response.status_code == 200
    assert member.get("/api/v1/auth/me").status_code == 401  # sessions revoked
    secret = response.json()["activation_link"].split("#", 1)[1]
    preview = owner.get(f"/api/v1/auth/invitations/{secret}").json()
    assert preview["returning"] is True
    again = TestClient(owner.app).post("/api/v1/auth/activate", json={"token": secret, "name": "Dev Kapoor", "password": "Falcon-Recovered-42"})
    assert again.status_code == 200
    owner_id = owner.get("/api/v1/auth/me").json()["user"]["id"]
    assert owner.post(f"/api/v1/members/{owner_id}/invitation", headers=WRITE).status_code == 403


def test_operator_can_recover_the_owner(owner: TestClient) -> None:
    from conftest import db_session
    from falcon.domains.identity.service import recover_owner

    with db_session() as db:
        _, _, secret = recover_owner(db)
    assert owner.get("/api/v1/auth/me").status_code == 401
    restored = TestClient(owner.app).post("/api/v1/auth/activate", json={"token": secret, "name": "Asha Raman", "password": "Restored-Access-2031"})
    assert restored.status_code == 200
    assert restored.json()["user"]["role"] == "owner"
    actions = [e["action"] for e in TestClient(owner.app, cookies=restored.cookies).get("/api/v1/audit").json()["events"]]
    assert "member.access_reset" in actions


def test_session_probe_never_errors(client: TestClient) -> None:
    assert client.get("/api/v1/auth/session").json() == {"account": None}
    client.post("/api/v1/setup", json=SETUP)
    body = client.get("/api/v1/auth/session").json()
    assert body["account"]["user"]["email"] == OWNER["email"]
