import os
import tempfile
import importlib
from chat_agents import db, auth


def test_init_and_user_create(tmp_path):
    # Reload db module to pick up new DB_PATH from environment
    dbfile = tmp_path / "zac_test.db"
    os.environ["ZAC_DB_PATH"] = str(dbfile)
    importlib.reload(db)
    db.init_db()
    # create a user
    salt, h = auth.make_pin_hash("1234")
    user_id = db.create_user(chat_id="testchat", phone=None, pin_salt=salt, pin_hash=h)
    assert isinstance(user_id, int)
    u = db.get_user_by_chat("testchat")
    assert u is not None
    assert u["chat_id"] == "testchat"


def test_balance_and_loans(tmp_path):
    # Reload db module to pick up new DB_PATH from environment
    dbfile = tmp_path / "zac_test2.db"
    os.environ["ZAC_DB_PATH"] = str(dbfile)
    importlib.reload(db)
    db.init_db()
    salt, h = auth.make_pin_hash("0000")
    uid = db.create_user(chat_id="c1_loans", phone=None, pin_salt=salt, pin_hash=h)
    bal = db.get_balance("c1_loans")
    assert bal == 0.0
    loan_id = db.create_loan("c1_loans", 5000, "business")
    assert isinstance(loan_id, int)
    loans = db.list_loans("c1_loans")
    assert len(loans) == 1
    assert loans[0]["amount"] == 5000
