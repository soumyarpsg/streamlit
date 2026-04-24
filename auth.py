"""
auth.py — Admin authentication for the MSR Dashboard
====================================================
A small self-contained auth module for Streamlit. Stores admin credentials in
the same SQLite file the dashboard already uses (`msr_data.db`) in a dedicated
`admin_users` table.

Features
--------
• Pre-seeded admin accounts (defined in `_SEED_ADMINS` below) — created on
  first run. Self-service sign-up is disabled.
• Sign in / Sign out
• PBKDF2-SHA256 password hashing with per-user salt (no plain-text passwords)
• Streamlit session-based login tracking
• A ready-made sidebar auth panel: `render_auth_sidebar()`

Only the standard library is used (`hashlib`, `secrets`, `sqlite3`) so no extra
pip installs are required.

Usage from your dashboard
-------------------------
    import auth
    is_admin = auth.render_auth_sidebar()   # draws the login panel
    if is_admin:
        # show upload controls, etc.
        ...

Rotating a seeded password
--------------------------
Either (a) edit `_SEED_ADMINS` below, delete that user's row from `admin_users`
in msr_data.db, and restart the app, or (b) connect to the DB and update the
`password_hash` + `salt` columns directly.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st

# ────────────────────────────────────────────────────────────────────────────
# Storage (shares msr_data.db with the dashboard so you only deal with 1 file)
# ────────────────────────────────────────────────────────────────────────────
DB_PATH     = Path("msr_data.db")
USERS_TABLE = "admin_users"

# PBKDF2 iteration count — high enough to be slow for attackers, fast for users
PBKDF2_ITERATIONS = 200_000

# Minimum password strength
MIN_PASSWORD_LEN = 6

# ────────────────────────────────────────────────────────────────────────────
# Pre-seeded admin accounts
# ────────────────────────────────────────────────────────────────────────────
# These accounts are created automatically on first app start. Seeding is
# idempotent — if an account with the given username already exists, its
# password is NOT overwritten. To rotate a password, delete the row from
# `admin_users` in msr_data.db and restart the app.
_SEED_ADMINS: list[tuple[str, str]] = [
    ("soumya.mukherjee1@rpsg.in", "marketingdatateam"),
    ("ajeet.bawa@rpsg.in",        "marketingdatateam"),
    ("manas.chattaraj@rpsg.in",   "marketingdatateam"),
]


def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_auth_db() -> None:
    """Create the admin_users table on first run AND seed the pre-configured
    admin accounts if they don't exist yet."""
    with _db_connect() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                salt          TEXT    NOT NULL,
                created_at    TEXT    NOT NULL,
                last_login    TEXT
            )
        """)
        conn.commit()
    _seed_admins()


def _seed_admins() -> None:
    """Create each account in `_SEED_ADMINS` if it doesn't exist already.
    Idempotent — safe to call on every import / every rerun."""
    now = datetime.now().isoformat(timespec="seconds")
    for username, password in _SEED_ADMINS:
        try:
            with _db_connect() as conn:
                already = conn.execute(
                    f"SELECT 1 FROM {USERS_TABLE} WHERE username = ?",
                    (username,),
                ).fetchone()
                if already:
                    continue  # don't overwrite existing accounts
                salt     = secrets.token_hex(16)
                pwd_hash = _hash_password(password, salt)
                conn.execute(
                    f"INSERT INTO {USERS_TABLE} "
                    f"(username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                    (username, pwd_hash, salt, now),
                )
                conn.commit()
        except Exception:
            # Never let a seeding failure crash the app; the user can still
            # sign in with any accounts that were seeded successfully.
            pass


# ────────────────────────────────────────────────────────────────────────────
# Password hashing (PBKDF2-SHA256 + per-user salt)
# ────────────────────────────────────────────────────────────────────────────
def _hash_password(password: str, salt_hex: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        PBKDF2_ITERATIONS,
    )
    return dk.hex()


def _validate_username(username: str) -> Optional[str]:
    """Return an error string, or None if the username is OK."""
    if not username:
        return "Username is required."
    if len(username) < 3:
        return "Username must be at least 3 characters."
    if len(username) > 128:
        return "Username must be 128 characters or fewer."
    # Allow email-format usernames (letters, digits, '.', '_', '+', '@', '-')
    if not re.match(r"^[A-Za-z0-9_.+@-]+$", username):
        return "Username may only contain letters, digits, '.', '_', '+', '@' and '-'."
    return None


def _validate_password(password: str) -> Optional[str]:
    if not password:
        return "Password is required."
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    return None


# ────────────────────────────────────────────────────────────────────────────
# Public API: sign in / sign out
# ────────────────────────────────────────────────────────────────────────────
def sign_in(username: str, password: str) -> Tuple[bool, str]:
    """Verify credentials and mark session as logged in."""
    username = (username or "").strip()
    password = password or ""
    if not username or not password:
        return False, "Username and password are required."

    with _db_connect() as conn:
        row = conn.execute(
            f"SELECT id, password_hash, salt FROM {USERS_TABLE} WHERE username = ?",
            (username,),
        ).fetchone()

    if not row:
        # Generic error — don't leak which half was wrong
        return False, "Invalid username or password."

    user_id, stored_hash, salt = row
    if _hash_password(password, salt) != stored_hash:
        return False, "Invalid username or password."

    # Update last_login
    with _db_connect() as conn:
        conn.execute(
            f"UPDATE {USERS_TABLE} SET last_login = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), user_id),
        )
        conn.commit()

    st.session_state["auth_user"]    = username
    st.session_state["auth_user_id"] = int(user_id)
    return True, f"Welcome, {username}!"


def sign_out() -> None:
    st.session_state.pop("auth_user", None)
    st.session_state.pop("auth_user_id", None)


def is_logged_in() -> bool:
    return bool(st.session_state.get("auth_user"))


def current_user() -> Optional[str]:
    return st.session_state.get("auth_user")


# ────────────────────────────────────────────────────────────────────────────
# Streamlit sidebar UI
# ────────────────────────────────────────────────────────────────────────────
def render_auth_sidebar() -> bool:
    """Draw the sign-in panel in the sidebar.

    Self-service sign-up is disabled — admin accounts are pre-seeded via
    `_SEED_ADMINS`. Returns True if the current session is logged in as
    an admin. Call this once per rerun, near the top of `main()`.
    """
    init_auth_db()

    with st.sidebar:
        st.markdown("### 🔐 Admin Access")

        if is_logged_in():
            uname = current_user()
            st.markdown(
                f"""<div style="background:#1e4430;border:1px solid #2A9D8F;
                               color:#8ff0a8;padding:.55rem .8rem;border-radius:8px;
                               font-size:.85rem;margin-bottom:.5rem;
                               word-break:break-all;">
                      ✅ Signed in as <b>{uname}</b>
                    </div>""",
                unsafe_allow_html=True,
            )
            if st.button("🚪 Sign Out", use_container_width=True, key="auth_signout"):
                sign_out()
                st.rerun()
            return True

        # Not logged in — sign-in form only (sign-up is disabled)
        st.caption(
            "Viewers can see the dashboard without signing in. "
            "Only authorised admins can upload or manage data."
        )

        username = st.text_input(
            "Username",
            key="auth_username_input",
            placeholder="name@rpsg.in",
            max_chars=128,
        )
        password = st.text_input(
            "Password",
            type="password",
            key="auth_password_input",
            placeholder="••••••••",
        )
        if st.button("🔓 Sign In", use_container_width=True,
                     key="auth_signin_btn", type="primary"):
            ok, msg = sign_in(username, password)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    return False
