import os

from chat_agents import db, auth


def test_profile_upsert_and_fetch(tmp_path):
    dbfile = tmp_path / "zac_profile.db"
    os.environ["ZAC_DB_PATH"] = str(dbfile)
    db.init_db()

    salt, h = auth.make_pin_hash("1234")
    user_id = db.create_user(chat_id="p1", phone=None, pin_salt=salt, pin_hash=h)

    db.upsert_profile(
        user_id=user_id,
        full_name="Jane Doe",
        national_id="12345678",
        employer="Acme Ltd",
        monthly_income=55000,
        consent=1,
    )

    prof = db.get_profile(user_id)
    assert prof is not None
    assert prof["full_name"] == "Jane Doe"
    assert prof["national_id"] == "12345678"
    assert prof["employer"] == "Acme Ltd"
    assert prof["monthly_income"] == 55000
    assert prof["consent"] == 1
