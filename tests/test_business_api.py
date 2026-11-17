"""Integration tests for Phase 2 CRUD Services and REST API endpoints."""

from datetime import datetime, timedelta, timezone
import uuid
from fastapi.testclient import TestClient


def _get_admin_headers(client: TestClient) -> dict[str, str]:
    """Register or login the default test admin user and return Authorization headers."""
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin@test.local", "password": "TestAdminPassword!123"},
    )
    token_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "TestAdminPassword!123"},
    )
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_customer_crud_lifecycle(client: TestClient):
    """Test creating, reading, listing, updating, and deleting a customer via REST API."""
    auth_headers = _get_admin_headers(client)
    # 1. Create Customer
    create_payload = {
        "full_name": "Nusrat Jahan",
        "phone_number": "+8801811223344",
        "email": "nusrat@example.com",
        "preferred_language": "bn",
        "notes": "VIP client",
    }
    resp = client.post("/api/v1/customers", json=create_payload)
    assert resp.status_code == 201
    customer = resp.json()
    customer_id = customer["id"]
    assert customer["full_name"] == "Nusrat Jahan"
    assert customer["preferred_language"] == "bn"

    # 2. Duplicate phone number returns 409 Conflict
    dup_resp = client.post("/api/v1/customers", json=create_payload)
    assert dup_resp.status_code == 409

    # 3. Get Customer by ID
    get_resp = client.get(f"/api/v1/customers/{customer_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["email"] == "nusrat@example.com"

    # 4. List Customers
    list_resp = client.get("/api/v1/customers", headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(c["id"] == customer_id for c in list_resp.json())

    # 5. Update Customer
    patch_resp = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"full_name": "Nusrat Jahan Chowdhury", "preferred_language": "en"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["full_name"] == "Nusrat Jahan Chowdhury"
    assert patch_resp.json()["preferred_language"] == "en"

    # 6. Delete Customer
    del_resp = client.delete(f"/api/v1/customers/{customer_id}")
    assert del_resp.status_code == 204

    # 7. Confirm 404 after deletion
    missing_resp = client.get(f"/api/v1/customers/{customer_id}")
    assert missing_resp.status_code == 404


def test_conversation_message_lead_and_appointment_endpoints(client: TestClient):
    """Test full end-to-end API flow across Customer -> Conversation -> Message, Lead, Appointment."""
    auth_headers = _get_admin_headers(client)
    # Create Customer
    cust_resp = client.post(
        "/api/v1/customers",
        json={
            "full_name": "Tanvir Ahmed",
            "phone_number": "+8801911556677",
            "email": "tanvir@example.com",
        },
    )
    assert cust_resp.status_code == 201
    customer_id = cust_resp.json()["id"]

    # Create Conversation
    conv_resp = client.post(
        "/api/v1/conversations",
        json={
            "customer_id": customer_id,
            "channel": "voice",
            "status": "active",
            "summary": "Initial inquiry call",
        },
    )
    assert conv_resp.status_code == 201
    conversation_id = conv_resp.json()["id"]
    assert conv_resp.json()["channel"] == "voice"

    # Create Messages in Conversation
    msg_resp = client.post(
        "/api/v1/messages",
        json={
            "conversation_id": conversation_id,
            "role": "user",
            "content": "I would like to book an appointment for tomorrow.",
            "metadata_json": {"sentiment": "positive"},
        },
    )
    assert msg_resp.status_code == 201
    message_id = msg_resp.json()["id"]

    # List Messages filtered by Conversation
    msg_list_resp = client.get(f"/api/v1/messages?conversation_id={conversation_id}")
    assert msg_list_resp.status_code == 200
    assert len(msg_list_resp.json()) == 1
    assert msg_list_resp.json()[0]["id"] == message_id

    # Update Message
    msg_patch = client.patch(
        f"/api/v1/messages/{message_id}",
        json={"content": "I would like to book a consultation for tomorrow morning."},
    )
    assert msg_patch.status_code == 200
    assert "morning" in msg_patch.json()["content"]

    # Create Lead linked to Customer and Conversation
    lead_resp = client.post(
        "/api/v1/leads",
        json={
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "source": "receptionist",
            "status": "qualified",
            "priority": "high",
            "score": 92,
            "notes": "High intent caller",
        },
    )
    assert lead_resp.status_code == 201
    lead_id = lead_resp.json()["id"]

    # Filter Leads by customer_id and status
    leads_list = client.get(
        f"/api/v1/leads?customer_id={customer_id}&status=qualified",
        headers=auth_headers,
    )
    assert leads_list.status_code == 200
    assert len(leads_list.json()) == 1
    assert leads_list.json()[0]["id"] == lead_id

    # Update Lead
    lead_patch = client.patch(
        f"/api/v1/leads/{lead_id}",
        json={"status": "converted", "score": 100},
    )
    assert lead_patch.status_code == 200
    assert lead_patch.json()["status"] == "converted"
    assert lead_patch.json()["score"] == 100

    # Create Appointment linked to Customer and Conversation
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    appt_resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "title": "Strategy Consultation",
            "scheduled_at": scheduled_at,
            "duration_minutes": 60,
            "status": "scheduled",
            "notes": "Confirm 1 hour prior",
        },
    )
    assert appt_resp.status_code == 201
    appointment_id = appt_resp.json()["id"]

    # List Appointments filtered by customer_id
    appt_list = client.get(f"/api/v1/appointments?customer_id={customer_id}")
    assert appt_list.status_code == 200
    assert len(appt_list.json()) == 1
    assert appt_list.json()[0]["id"] == appointment_id

    # Update Appointment
    appt_patch = client.patch(
        f"/api/v1/appointments/{appointment_id}",
        json={"status": "confirmed", "duration_minutes": 45},
    )
    assert appt_patch.status_code == 200
    assert appt_patch.json()["status"] == "confirmed"
    assert appt_patch.json()["duration_minutes"] == 45

    # Close Conversation
    conv_patch = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"status": "completed", "summary": "Appointment booked and lead converted."},
    )
    assert conv_patch.status_code == 200
    assert conv_patch.json()["status"] == "completed"


def test_creating_entities_with_nonexistent_foreign_keys_returns_404(client: TestClient):
    """Ensure routes validate parent entity existence and return 404 Not Found."""
    fake_uuid = str(uuid.uuid4())

    conv_resp = client.post(
        "/api/v1/conversations",
        json={"customer_id": fake_uuid, "channel": "web"},
    )
    assert conv_resp.status_code == 404

    msg_resp = client.post(
        "/api/v1/messages",
        json={"conversation_id": fake_uuid, "role": "user", "content": "Hi"},
    )
    assert msg_resp.status_code == 404

    lead_resp = client.post(
        "/api/v1/leads",
        json={"customer_id": fake_uuid, "source": "web"},
    )
    assert lead_resp.status_code == 404

    appt_resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": fake_uuid,
            "title": "Test",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert appt_resp.status_code == 404


def test_patch_customer_duplicate_phone_or_email_returns_409(client: TestClient):
    """Updating a customer to use another customer's phone or email must return 409 Conflict."""
    c1 = client.post(
        "/api/v1/customers",
        json={"full_name": "Customer One", "phone_number": "+8801700000001", "email": "c1@example.com"},
    ).json()
    c2 = client.post(
        "/api/v1/customers",
        json={"full_name": "Customer Two", "phone_number": "+8801700000002", "email": "c2@example.com"},
    ).json()

    dup_phone = client.patch(
        f"/api/v1/customers/{c2['id']}",
        json={"phone_number": c1["phone_number"]},
    )
    assert dup_phone.status_code == 409

    dup_email = client.patch(
        f"/api/v1/customers/{c2['id']}",
        json={"email": c1["email"]},
    )
    assert dup_email.status_code == 409


def test_patch_lead_or_appointment_with_missing_conversation_returns_404(client: TestClient):
    """Updating a lead or appointment with a non-existent conversation_id must return 404 Not Found."""
    cust = client.post(
        "/api/v1/customers",
        json={"full_name": "Patch FK User", "phone_number": "+8801700000099"},
    ).json()
    lead = client.post(
        "/api/v1/leads",
        json={"customer_id": cust["id"], "source": "web"},
    ).json()
    appt = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": cust["id"],
            "title": "Checkup",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        },
    ).json()

    fake_conv_id = str(uuid.uuid4())
    lead_patch = client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={"conversation_id": fake_conv_id},
    )
    assert lead_patch.status_code == 404

    appt_patch = client.patch(
        f"/api/v1/appointments/{appt['id']}",
        json={"conversation_id": fake_conv_id},
    )
    assert appt_patch.status_code == 404

