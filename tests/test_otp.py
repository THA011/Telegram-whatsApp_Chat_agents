import os
import tempfile
from chat_agents import db
from chat_agents import otp
from chat_agents import zac_bot


def test_create_and_verify_otp(tmp_path):
    dbfile = tmp_path / "zac_otp.db"
    os.environ["ZAC_DB_PATH"] = str(dbfile)
    db.init_db()
    # create a user with phone
    uid = db.create_user(chat_id="u1", phone="whatsapp:+10000000000", pin_salt="", pin_hash="")
    assert isinstance(uid, int)

    code, row = otp.create_and_store_otp("u1")
    assert isinstance(code, str) and len(code) == 6
    assert isinstance(row, int)

    ok = otp.verify_otp("u1", code)
    assert ok is True

    # consumed; subsequent verify should be False
    ok2 = otp.verify_otp("u1", code)
    assert ok2 is False


def test_expired_otp(tmp_path):
    dbfile = tmp_path / "zac_otp2.db"
    os.environ["ZAC_DB_PATH"] = str(dbfile)
    db.init_db()
    db.create_user(chat_id="u2", phone="whatsapp:+20000000000", pin_salt="", pin_hash="")
    code, _ = otp.create_and_store_otp("u2", lifetime_seconds=-1)
    assert otp.verify_otp("u2", code) is False


def test_send_otp_cmd_variants(tmp_path, monkeypatch):
    dbfile = tmp_path / "zac_otp3.db"
    os.environ["ZAC_DB_PATH"] = str(dbfile)
    db.init_db()
    db.create_user(chat_id="u3", phone="whatsapp:+30000000000", pin_salt="", pin_hash="")

    # Test 1: When send_via_twilio is not available (Twilio not configured), dev mode returns OTP code
    resp = zac_bot.send_otp_cmd("u3")
    assert "OTP" in resp  # Either "OTP sent" or "OTP (dev): xxxxxx"
    assert isinstance(resp, str) and len(resp) > 0

    # Test 2: Verify second call also works
    resp2 = zac_bot.send_otp_cmd("u3")
    assert "OTP" in resp2
    assert isinstance(resp2, str) and len(resp2) > 0
