"""Unit and integration tests for Phase 6 Security, JWT Auth, and Rate Limiting."""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.security import create_access_token, get_password_hash, verify_password
from backend.database.models import User


def test_password_hashing_and_jwt_creation():
    """Verify bcrypt password hashing via passlib and HS256 JWT token generation."""
    raw_password = "StrongAdminPassword!2026"
    hashed = get_password_hash(raw_password)
    assert hashed != raw_password
    assert hashed.startswith("$2")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

    token = create_access_token(data={"sub": "admin@aiemployee.local"})
    assert isinstance(token, str)
    assert len(token) > 20


def test_auth_register_login_and_protected_endpoints(
    client: TestClient,
    db_session: Session,
):
    """Test user registration, OAuth2 login, 200 OK with JWT, and 401 Unauthorized without JWT."""
    # 1. Accessing protected endpoints WITHOUT token must return 401 Unauthorized
    unauth_leads = client.get("/api/v1/leads")
    assert unauth_leads.status_code == 401

    unauth_customers = client.get("/api/v1/customers")
    assert unauth_customers.status_code == 401

    # 2. Register initial admin user via POST /api/v1/auth/register
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@aiemployee.com",
            "password": "SuperSecretAdmin!123",
            "role": "admin",
        },
    )
    assert reg_resp.status_code in (200, 201)
    reg_data = reg_resp.json()
    assert reg_data["email"] == "owner@aiemployee.com"
    assert reg_data["role"] == "admin"
    assert reg_data["is_active"] is True
    assert "hashed_password" not in reg_data

    # Confirm user is stored in SQLite
    db_user = db_session.query(User).filter(User.email == "owner@aiemployee.com").first()
    assert db_user is not None
    assert verify_password("SuperSecretAdmin!123", db_user.hashed_password)

    # 3. Attempting open registration after initial admin exists should be forbidden (403)
    second_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "attacker@aiemployee.com",
            "password": "AttackerPassword!123",
        },
    )
    assert second_reg.status_code == 403

    # 4. Login via OAuth2PasswordRequestForm (form data: username & password)
    login_resp = client.post(
        "/api/v1/auth/login",
        data={
            "username": "owner@aiemployee.com",
            "password": "SuperSecretAdmin!123",
        },
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"].lower() == "bearer"
    jwt_token = token_data["access_token"]

    # 5. Access protected endpoints (/api/v1/leads and /api/v1/customers) WITH token -> 200 OK
    auth_headers = {"Authorization": f"Bearer {jwt_token}"}
    leads_resp = client.get("/api/v1/leads", headers=auth_headers)
    assert leads_resp.status_code == 200
    assert isinstance(leads_resp.json(), list)

    customers_resp = client.get("/api/v1/customers", headers=auth_headers)
    assert customers_resp.status_code == 200
    assert isinstance(customers_resp.json(), list)

    # 6. Invalid login password returns 401 Unauthorized
    bad_login = client.post(
        "/api/v1/auth/login",
        data={
            "username": "owner@aiemployee.com",
            "password": "WrongPassword!999",
        },
    )
    assert bad_login.status_code == 401


def test_chat_receptionist_rate_limit_enforced(client: TestClient):
    """Verify slowapi rate limiter returns 429 Too Many Requests after exceeding 10 requests/minute."""
    cust = client.post(
        "/api/v1/customers",
        json={"full_name": "Rate Limit User", "phone_number": "+8801700998877"},
    ).json()
    conv = client.post(
        "/api/v1/conversations",
        json={"customer_id": cust["id"], "channel": "web"},
    ).json()

    mock_rec_resp = MagicMock()
    mock_rec_resp.text = "Hello! How can I help?"

    with (
        patch(
            "backend.agents.receptionist.search_knowledge_base",
            return_value={"query": "hi", "answer": "Hello", "contexts": ["Hello"]},
        ),
        patch("backend.agents.receptionist.genai.Client") as mock_rec_cls,
        patch("backend.agents.analyst.AIBusinessAnalyst.analyze_conversation"),
    ):
        mock_rec_client = MagicMock()
        mock_rec_client.models.generate_content.return_value = mock_rec_resp
        mock_rec_cls.return_value = mock_rec_client

        status_codes = []
        for i in range(12):
            resp = client.post(
                "/api/v1/chat/receptionist",
                json={
                    "customer_id": cust["id"],
                    "conversation_id": conv["id"],
                    "content": f"Message {i + 1}",
                },
            )
            status_codes.append(resp.status_code)

        assert 200 in status_codes
        assert 429 in status_codes


def test_jwt_missing_exp_claim_is_rejected(client: TestClient):
    """Verify JWT tokens missing an explicit 'exp' claim are strictly rejected with 401."""
    from jose import jwt
    from backend.core.config import get_settings

    settings = get_settings()
    token_without_exp = jwt.encode(
        {"sub": "owner@aiemployee.com"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    resp = client.get(
        "/api/v1/leads",
        headers={"Authorization": f"Bearer {token_without_exp}"},
    )
    assert resp.status_code == 401
