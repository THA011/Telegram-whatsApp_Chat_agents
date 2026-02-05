"""Lightweight SQLite DB helper for zac_sacco_credit_bot features."""
import os
import sqlite3
from datetime import datetime
from typing import Optional, Tuple

DB_PATH = os.environ.get("ZAC_DB_PATH", os.path.join(os.path.dirname(__file__), "zac.db"))


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Create tables if they don't exist."""
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE,
                phone TEXT,
                pin_salt TEXT,
                pin_hash TEXT,
                created_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                balance REAL DEFAULT 0.0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                reason TEXT,
                status TEXT,
                created_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        # OTP codes table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS otps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                code_hash TEXT,
                expires_at TEXT,
                consumed INTEGER DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                full_name TEXT,
                national_id TEXT,
                employer TEXT,
                monthly_income REAL,
                consent INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        c.commit()


# User functions

def create_user(chat_id: str, phone: Optional[str], pin_salt: str, pin_hash: str) -> int:
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users (chat_id, phone, pin_salt, pin_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (chat_id, phone, pin_salt, pin_hash, now),
        )
        c.commit()
        cur.execute("SELECT id FROM users WHERE chat_id = ?", (chat_id,))
        row = cur.fetchone()
        user_id = row[0]
        # ensure account exists
        cur.execute("INSERT OR IGNORE INTO accounts (user_id, balance) VALUES (?, ?)", (user_id, 0.0))
        c.commit()
        return user_id


def get_user_by_chat(chat_id: str) -> Optional[dict]:
    with _conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id, chat_id, phone, pin_salt, pin_hash, created_at FROM users WHERE chat_id = ?", (chat_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "chat_id": row[1],
            "phone": row[2],
            "pin_salt": row[3],
            "pin_hash": row[4],
            "created_at": row[5],
        }


# Account functions

def get_balance(chat_id: str) -> Optional[float]:
    user = get_user_by_chat(chat_id)
    if not user:
        return None
    with _conn() as c:
        cur = c.cursor()
        cur.execute("SELECT balance FROM accounts WHERE user_id = ?", (user["id"],))
        row = cur.fetchone()
        return float(row[0]) if row else 0.0


# Loan functions

def create_loan(chat_id: str, amount: float, reason: str) -> Optional[int]:
    user = get_user_by_chat(chat_id)
    if not user:
        return None
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO loans (user_id, amount, reason, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (user["id"], float(amount), reason, "pending", now),
        )
        c.commit()
        return cur.lastrowid


def list_loans(chat_id: str) -> list:
    user = get_user_by_chat(chat_id)
    if not user:
        return []
    with _conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id, amount, reason, status, created_at FROM loans WHERE user_id = ? ORDER BY id DESC", (user["id"],))
        rows = cur.fetchall()
        return [dict(id=r[0], amount=r[1], reason=r[2], status=r[3], created_at=r[4]) for r in rows]

# OTP functions

def create_otp_for_user(chat_id: str, code_hash: str, expires_at: str) -> Optional[int]:
    user = get_user_by_chat(chat_id)
    if not user:
        return None
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO otps (user_id, code_hash, expires_at, consumed, created_at) VALUES (?, ?, ?, 0, ?)",
            (user["id"], code_hash, expires_at, datetime.utcnow().isoformat()),
        )
        c.commit()
        return cur.lastrowid


def consume_otp(chat_id: str, code_hash: str) -> bool:
    user = get_user_by_chat(chat_id)
    if not user:
        return False
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT id, expires_at, consumed FROM otps WHERE user_id = ? AND code_hash = ? ORDER BY id DESC LIMIT 1",
            (user["id"], code_hash),
        )
        row = cur.fetchone()
        if not row:
            return False
        id_, expires_at, consumed = row
        if consumed:
            return False
        if datetime.fromisoformat(expires_at) < datetime.utcnow():
            return False
        cur.execute("UPDATE otps SET consumed = 1 WHERE id = ?", (id_,))
        c.commit()
        return True


# Profile functions

def upsert_profile(
    user_id: int,
    full_name: str,
    national_id: str,
    employer: str,
    monthly_income: float,
    consent: int,
) -> None:
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            INSERT INTO profiles (user_id, full_name, national_id, employer, monthly_income, consent, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                national_id = excluded.national_id,
                employer = excluded.employer,
                monthly_income = excluded.monthly_income,
                consent = excluded.consent,
                updated_at = excluded.updated_at
            """,
            (user_id, full_name, national_id, employer, float(monthly_income), int(consent), now, now),
        )
        c.commit()


def get_profile(user_id: int) -> Optional[dict]:
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT user_id, full_name, national_id, employer, monthly_income, consent, created_at, updated_at FROM profiles WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "user_id": row[0],
            "full_name": row[1],
            "national_id": row[2],
            "employer": row[3],
            "monthly_income": row[4],
            "consent": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
