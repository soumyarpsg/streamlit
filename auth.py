"""
auth.py — Admin authentication for the MSR Dashboard
====================================================
A small self-contained auth module for Streamlit. Stores admin credentials in
the same SQLite file the dashboard already uses (`msr_data.db`) in a dedicated
`admin_users` table.

Features
--------
• Sign up (create admin account)
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


def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_auth_db() -> None:
    """Create the admin_users table on first run."""
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
    if len(username) > 32:
        return "Username must be 32 characters or fewer."
    if not re.match(r"^[A-Za-z0-9_.-]+$", username):
        return "Username may only contain letters, digits, '.', '_' and '-'."
    return None


def _validate_password(password: str) -> Optional[str]:
    if not password:
        return "Password is required."
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    return None


# ────────────────────────────────────────────────────────────────────────────
# Public API: sign up / sign in / sign out
# ────────────────────────────────────────────────────────────────────────────
def sign_up(username: str, password: str) -> Tuple[bool, str]:
    """Create a new admin account. Returns (ok, message)."""
    username = (username or "").strip()
    password = password or ""

    err = _validate_username(username) or _validate_password(password)
    if err:
        return False, err

    salt = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt)
    now = datetime.now().isoformat(timespec="seconds")

    try:
        with _db_connect() as conn:
            conn.execute(
                f"INSERT INTO {USERS_TABLE} "
                f"(username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (username, pwd_hash, salt, now),
            )
            conn.commit()
        return True, f"Account created for '{username}'. You can sign in now."
    except sqlite3.IntegrityError:
        return False, f"Username '{username}' is already taken."
    except Exception as e:
        return False, f"Could not create account: {e}"


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


def user_count() -> int:
    """Count of admin accounts — handy for 'No admins yet, sign up' banners."""
    try:
        with _db_connect() as conn:
            return int(conn.execute(
                f"SELECT COUNT(*) FROM {USERS_TABLE}"
            ).fetchone()[0])
    except sqlite3.OperationalError:
        return 0


# ────────────────────────────────────────────────────────────────────────────
# Streamlit sidebar UI
# ────────────────────────────────────────────────────────────────────────────
def render_auth_sidebar() -> bool:
    """Draw the login / signup panel in the sidebar.

    Returns True if the current session is logged in as an admin.
    Call this once per rerun, near the top of `main()`.
    """
    init_auth_db()

    with st.sidebar:
        st.markdown("### 🔐 Admin Access")

        if is_logged_in():
            uname = current_user()
            st.markdown(
                f"""<div style="background:#1e4430;border:1px solid #2A9D8F;
                               color:#8ff0a8;padding:.55rem .8rem;border-radius:8px;
                               font-size:.85rem;margin-bottom:.5rem;">
                      ✅ Signed in as <b>{uname}</b>
                    </div>""",
                unsafe_allow_html=True,
            )
            if st.button("🚪 Sign Out", use_container_width=True, key="auth_signout"):
                sign_out()
                st.rerun()
            return True

        # Not logged in — show sign-in / sign-up form
        st.caption(
            "Viewers can see the dashboard without signing in. "
            "Only admins can upload or manage data."
        )

        n_users = user_count()
        default_mode_idx = 1 if n_users == 0 else 0   # first-run → default to Sign Up
        if n_users == 0:
            st.info("No admin accounts exist yet. Create the first one below.")

        mode = st.radio(
            "Action",
            ["Sign In", "Sign Up"],
            index=default_mode_idx,
            horizontal=True,
            label_visibility="collapsed",
            key="auth_mode",
        )

        username = st.text_input(
            "Username",
            key="auth_username_input",
            placeholder="your.username",
            max_chars=32,
        )
        password = st.text_input(
            "Password",
            type="password",
            key="auth_password_input",
            placeholder="••••••••",
        )

        if mode == "Sign In":
            if st.button("🔓 Sign In", use_container_width=True,
                         key="auth_signin_btn", type="primary"):
                ok, msg = sign_in(username, password)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            confirm = st.text_input(
                "Confirm Password",
                type="password",
                key="auth_confirm_input",
                placeholder="••••••••",
            )
            if st.button("📝 Create Admin Account",
                         use_container_width=True, key="auth_signup_btn",
                         type="primary"):
                if password != confirm:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = sign_up(username, password)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

    return False
