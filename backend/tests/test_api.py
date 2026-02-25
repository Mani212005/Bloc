# In-memory SQLite for tests; covers assignment engine, webhook, callers CRUD, leads.
# Engine, schema, and db/client fixtures are provided by conftest.py.
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from app.models import Caller, CallerState, CallerStatus, Lead, LeadAssignmentStatus


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_caller(db, name="Alice", daily_limit=5, states=None, status=CallerStatus.ACTIVE):
    c = Caller(
        id=uuid.uuid4(),
        name=name,
        role="Agent",
        languages=["english"],
        daily_limit=daily_limit,
        status=status,
    )
    db.add(c)
    for s in (states or []):
        db.add(CallerState(caller_id=c.id, state=s))
    db.commit()
    db.refresh(c)
    return c


def make_lead(db, phone, state=None, timestamp=None):
    lead = Lead(
        id=uuid.uuid4(),
        phone=phone,
        timestamp_from_sheet=timestamp or datetime.now(timezone.utc),
        state=state,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def webhook_payload(**overrides):
    base = {
        "name": "Test Lead",
        "phone": "9999999999",
        "timestamp": "2026-02-25T10:00:00Z",
        "lead_source": "google_sheet",
        "city": "Mumbai",
        "state": "maharashtra",
        "metadata": {},
    }
    base.update(overrides)
    return base


# ── Assignment engine unit tests ─────────────────────────────────────────────

class TestAssignmentEngine:
    def test_state_based_assignment(self, db):
        from app.services.assignment_engine import assign_lead

        alice = make_caller(db, name="Alice", states=["maharashtra"])
        _bob  = make_caller(db, name="Bob",   states=["karnataka"])
        lead  = make_lead(db, phone="1111111111", state="maharashtra")

        assignment = assign_lead(db, lead)
        db.commit()

        assert str(assignment.caller_id) == str(alice.id)
        assert assignment.assignment_reason == "state_round_robin"

    def test_global_fallback_when_no_state_callers(self, db):
        from app.services.assignment_engine import assign_lead

        alice = make_caller(db, name="Alice", states=["maharashtra"])
        lead  = make_lead(db, phone="2222222222", state="kerala")

        assignment = assign_lead(db, lead)
        db.commit()

        assert str(assignment.caller_id) == str(alice.id)
        assert assignment.assignment_reason == "global_round_robin"

    def test_round_robin_distributes_fairly(self, db):
        from app.services.assignment_engine import assign_lead

        alice = make_caller(db, name="Alice", daily_limit=0)
        bob   = make_caller(db, name="Bob",   daily_limit=0)

        assigned = []
        for i in range(4):
            lead = make_lead(db, phone=f"30000000{i:02d}")
            a = assign_lead(db, lead)
            db.commit()
            assigned.append(str(a.caller_id))

        assert assigned.count(str(alice.id)) == 2
        assert assigned.count(str(bob.id)) == 2

    def test_daily_cap_enforced(self, db):
        from app.services.assignment_engine import assign_lead

        alice = make_caller(db, name="Alice", daily_limit=2)

        caller_ids = []
        for i in range(3):
            lead = make_lead(db, phone=f"40000000{i:02d}")
            a = assign_lead(db, lead)
            db.commit()
            caller_ids.append(a.caller_id)

        assert caller_ids[0] is not None
        assert caller_ids[1] is not None
        assert caller_ids[2] is None  # cap reached

    def test_unlimited_cap_zero(self, db):
        from app.services.assignment_engine import assign_lead

        alice = make_caller(db, name="Alice", daily_limit=0)

        for i in range(10):
            lead = make_lead(db, phone=f"50000000{i:02d}")
            a = assign_lead(db, lead)
            db.commit()
            assert a.caller_id is not None

    def test_paused_caller_excluded(self, db):
        from app.services.assignment_engine import assign_lead

        make_caller(db, name="Paused", status="paused")
        lead = make_lead(db, phone="6000000000")
        a = assign_lead(db, lead)
        db.commit()

        assert a.status == LeadAssignmentStatus.UNASSIGNED
        assert a.caller_id is None

    def test_all_callers_at_cap_goes_unassigned(self, db):
        from app.services.assignment_engine import assign_lead

        make_caller(db, name="Alice", daily_limit=1)

        lead1 = make_lead(db, phone="7000000001")
        assign_lead(db, lead1)
        db.commit()

        lead2 = make_lead(db, phone="7000000002")
        a = assign_lead(db, lead2)
        db.commit()

        assert a.status == LeadAssignmentStatus.UNASSIGNED

    def test_forced_caller_manual_reassign(self, db):
        from app.services.assignment_engine import assign_lead

        alice = make_caller(db, name="Alice", daily_limit=0)
        bob   = make_caller(db, name="Bob",   daily_limit=0)
        lead  = make_lead(db, phone="8800000001")

        # First assign to alice via normal flow
        a1 = assign_lead(db, lead)
        db.commit()

        # Force reassign to bob
        lead2 = make_lead(db, phone="8800000002")
        a2 = assign_lead(db, lead2, forced_caller_id=bob.id)
        db.commit()

        assert str(a2.caller_id) == str(bob.id)
        assert a2.assignment_reason == "manual_reassign"


# ── Webhook API tests ────────────────────────────────────────────────────────

class TestWebhook:
    def test_webhook_assigns_lead(self, client, db):
        make_caller(db, name="Alice", daily_limit=0)
        res = client.post("/api/leads/webhook", json=webhook_payload())
        assert res.status_code == 200
        data = res.json()
        assert data["assignment_status"] == "assigned"
        assert data["assigned_caller_id"] is not None

    def test_webhook_idempotent(self, client, db):
        make_caller(db, name="Alice", daily_limit=0)
        payload = webhook_payload()
        r1 = client.post("/api/leads/webhook", json=payload)
        r2 = client.post("/api/leads/webhook", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]

    def test_webhook_rejects_bad_secret(self, client):
        with patch.dict("os.environ", {"WEBHOOK_SECRET": "super-secret"}):
            res = client.post(
                "/api/leads/webhook",
                json=webhook_payload(),
                headers={"X-Webhook-Secret": "wrong"},
            )
        assert res.status_code == 401

    def test_webhook_accepts_correct_secret(self, client, db):
        make_caller(db, name="Alice", daily_limit=0)
        with patch.dict("os.environ", {"WEBHOOK_SECRET": "super-secret"}):
            res = client.post(
                "/api/leads/webhook",
                json=webhook_payload(phone="8888888888"),
                headers={"X-Webhook-Secret": "super-secret"},
            )
        assert res.status_code == 200

    def test_webhook_unassigned_when_no_callers(self, client):
        res = client.post("/api/leads/webhook", json=webhook_payload())
        assert res.status_code == 200
        assert res.json()["assignment_status"] == "unassigned"

    def test_webhook_missing_required_fields(self, client):
        res = client.post("/api/leads/webhook", json={"name": "No phone"})
        assert res.status_code == 422

    def test_webhook_metadata_optional(self, client, db):
        make_caller(db, name="Alice", daily_limit=0)
        payload = webhook_payload()
        del payload["metadata"]
        res = client.post("/api/leads/webhook", json=payload)
        assert res.status_code == 200


# ── Caller CRUD tests ────────────────────────────────────────────────────────

class TestCallers:
    def test_create_caller(self, client):
        res = client.post("/api/callers", json={
            "name": "Bob",
            "role": "Sales",
            "languages": ["hindi"],
            "daily_limit": 10,
            "assigned_states": ["delhi"],
            "status": "active",
        })
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Bob"
        assert data["assigned_states"] == ["delhi"]
        assert data["leads_assigned_today"] == 0

    def test_list_callers(self, client, db):
        make_caller(db, name="Charlie", daily_limit=0)
        res = client.get("/api/callers")
        assert res.status_code == 200
        names = [c["name"] for c in res.json()]
        assert "Charlie" in names

    def test_update_caller(self, client, db):
        c = make_caller(db, name="Dave", daily_limit=5)
        res = client.put(f"/api/callers/{c.id}", json={
            "daily_limit": 20,
            "assigned_states": ["goa"],
        })
        assert res.status_code == 200
        data = res.json()
        assert data["daily_limit"] == 20
        assert "goa" in data["assigned_states"]

    def test_patch_caller_status(self, client, db):
        c = make_caller(db, name="Eve", daily_limit=0)
        res = client.patch(f"/api/callers/{c.id}/status", json={"status": "paused"})
        assert res.status_code == 200
        assert res.json()["status"] == "paused"

    def test_patch_caller_status_reactivate(self, client, db):
        c = make_caller(db, name="Eve2", status="paused", daily_limit=0)
        res = client.patch(f"/api/callers/{c.id}/status", json={"status": "active"})
        assert res.status_code == 200
        assert res.json()["status"] == "active"

    def test_delete_caller_pauses(self, client, db):
        c = make_caller(db, name="Frank", daily_limit=0)
        res = client.delete(f"/api/callers/{c.id}")
        assert res.status_code == 204

    def test_create_caller_invalid_limit(self, client):
        res = client.post("/api/callers", json={
            "name": "Bad",
            "daily_limit": -1,
            "assigned_states": [],
        })
        assert res.status_code == 400

    def test_create_caller_missing_name(self, client):
        res = client.post("/api/callers", json={"daily_limit": 5})
        assert res.status_code == 422

    def test_get_nonexistent_caller(self, client):
        res = client.put(f"/api/callers/{uuid.uuid4()}", json={"daily_limit": 5})
        assert res.status_code == 404

    def test_caller_leads_assigned_today(self, client, db):
        make_caller(db, name="Grace", daily_limit=0)
        client.post("/api/leads/webhook", json=webhook_payload())
        res = client.get("/api/callers")
        grace = next(c for c in res.json() if c["name"] == "Grace")
        assert grace["leads_assigned_today"] == 1


# ── Lead list & reassign tests ───────────────────────────────────────────────

class TestLeads:
    def test_list_leads_empty(self, client):
        res = client.get("/api/leads")
        assert res.status_code == 200
        assert res.json() == []

    def test_list_leads_after_webhook(self, client, db):
        make_caller(db, name="Grace", daily_limit=0)
        client.post("/api/leads/webhook", json=webhook_payload())
        res = client.get("/api/leads")
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_filter_leads_by_state(self, client, db):
        make_caller(db, name="Grace", daily_limit=0)
        client.post("/api/leads/webhook", json=webhook_payload(state="maharashtra"))
        client.post("/api/leads/webhook", json=webhook_payload(
            phone="1112223333", state="karnataka", timestamp="2026-02-25T11:00:00Z"
        ))
        res = client.get("/api/leads?state=maharashtra")
        assert res.status_code == 200
        leads = res.json()
        assert len(leads) == 1
        assert leads[0]["state"] == "maharashtra"

    def test_filter_leads_by_caller(self, client, db):
        alice = make_caller(db, name="Alice", daily_limit=0)
        bob   = make_caller(db, name="Bob",   daily_limit=0)
        client.post("/api/leads/webhook", json=webhook_payload(phone="1000000001"))
        client.post("/api/leads/webhook", json=webhook_payload(phone="1000000002", timestamp="2026-02-25T12:00:00Z"))
        res = client.get(f"/api/leads?caller_id={alice.id}")
        assert res.status_code == 200
        # At least one lead should be assigned to alice via round robin
        assert len(res.json()) >= 1

    def test_search_leads_by_phone(self, client, db):
        make_caller(db, name="Grace", daily_limit=0)
        client.post("/api/leads/webhook", json=webhook_payload(phone="5551234567"))
        res = client.get("/api/leads?search=5551234567")
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_get_lead_detail(self, client, db):
        make_caller(db, name="Grace", daily_limit=0)
        r = client.post("/api/leads/webhook", json=webhook_payload())
        lead_id = r.json()["id"]
        res = client.get(f"/api/leads/{lead_id}")
        assert res.status_code == 200
        assert res.json()["id"] == lead_id

    def test_get_nonexistent_lead(self, client):
        res = client.get(f"/api/leads/{uuid.uuid4()}")
        assert res.status_code == 404

    def test_reassign_lead(self, client, db):
        alice = make_caller(db, name="Alice", daily_limit=0)
        bob   = make_caller(db, name="Bob",   daily_limit=0)

        r = client.post("/api/leads/webhook", json=webhook_payload())
        lead_id = r.json()["id"]

        res = client.patch(f"/api/leads/{lead_id}/reassign", json={"caller_id": str(bob.id)})
        assert res.status_code == 200
        assert str(res.json()["assigned_caller_id"]) == str(bob.id)
        assert res.json()["assignment_reason"] == "manual_reassign"

    def test_reassign_nonexistent_lead(self, client, db):
        c = make_caller(db, name="Alice", daily_limit=0)
        res = client.patch(f"/api/leads/{uuid.uuid4()}/reassign", json={"caller_id": str(c.id)})
        assert res.status_code == 404

    def test_reassign_to_auto(self, client, db):
        """Passing caller_id=null triggers auto round-robin reassign."""
        make_caller(db, name="Alice", daily_limit=0)
        r = client.post("/api/leads/webhook", json=webhook_payload())
        lead_id = r.json()["id"]

        res = client.patch(f"/api/leads/{lead_id}/reassign", json={"caller_id": None})
        assert res.status_code == 200

