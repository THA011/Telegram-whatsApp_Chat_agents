import os
import sys
import types
from chat_agents import db, message_queue


def test_enqueue_and_process_raw_message(tmp_path, monkeypatch):
    dbfile = tmp_path / "zac_worker.db"
    os.environ["ZAC_DB_PATH"] = str(dbfile)
    db.init_db()

    # Set Twilio env to simulate configured production
    os.environ["TWILIO_ACCOUNT_SID"] = "AC123"
    os.environ["TWILIO_AUTH_TOKEN"] = "token"
    os.environ["TWILIO_WHATSAPP_NUMBER"] = "+15005550006"

    # Create fake twilio.rest.Client
    recorded = []

    rest_mod = types.ModuleType("twilio.rest")

    class FakeClient:
        def __init__(self, sid, token):
            self.sid = sid
            self.token = token

            class Msg:
                def create(self, **kwargs):
                    recorded.append(kwargs)

            self.messages = Msg()

    rest_mod.Client = FakeClient

    # Inject fake modules
    sys.modules["twilio"] = types.ModuleType("twilio")
    sys.modules["twilio.rest"] = rest_mod

    # Directly call _process_job with a whatsapp job
    job = {"platform": "whatsapp", "to": "whatsapp:+100", "body": "hi otp"}
    # Should not raise and recorded should get one item
    message_queue._process_job(job)
    assert len(recorded) == 1
    assert recorded[0]["body"] == "hi otp"
    assert recorded[0]["to"].startswith("whatsapp:")


def test_enqueue_otp_for_user(tmp_path, monkeypatch):
    dbfile = tmp_path / "zac_worker2.db"
    os.environ["ZAC_DB_PATH"] = str(dbfile)
    db.init_db()
    db.create_user(chat_id="u4", phone="whatsapp:+40000000000", pin_salt="", pin_hash="")

    # Monkeypatch enqueue_raw_message to capture job
    called = {}

    def fake_enqueue(platform, to, body):
        called["platform"] = platform
        called["to"] = to
        called["body"] = body
        return {"job_id": "x"}

    monkeypatch.setattr(message_queue, "enqueue_raw_message", fake_enqueue)

    meta = message_queue.enqueue_otp_for_user("u4")
    assert meta == {"job_id": "x"}
    assert called["platform"] == "whatsapp"
    assert called["to"].startswith("whatsapp:")
    assert "OTP" in called["body"]
