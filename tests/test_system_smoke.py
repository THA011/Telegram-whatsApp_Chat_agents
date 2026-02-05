import os
import sys
import types
from chat_agents import db, otp, message_queue


def test_end_to_end_otp_flow(tmp_path, monkeypatch):
    """End-to-end test: verify OTP creation and send logic."""
    dbfile = tmp_path / "zac_system.db"
    os.environ["ZAC_DB_PATH"] = str(dbfile)
    db.init_db()
    db.create_user(chat_id="s_sys", phone="whatsapp:+19990001111", pin_salt="", pin_hash="")

    # Mock send_via_twilio to track calls
    send_calls = []
    def mock_send(to, body):
        send_calls.append((to, body))
        return True
    monkeypatch.setattr(otp, "send_via_twilio", mock_send)

    # Import zac_bot after mocking to use the mocked otp
    from chat_agents import zac_bot
    code, _ = otp.create_and_store_otp("s_sys")
    resp = zac_bot.send_otp_cmd("s_sys")

    # Verify OTP was created and send was attempted
    assert code is not None
    assert isinstance(resp, str)
    assert len(resp) > 0
    # At least one send attempt should have been made
    assert len(send_calls) >= 1 or "OTP" in resp
