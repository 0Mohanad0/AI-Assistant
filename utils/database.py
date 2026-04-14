import os
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import psycopg
import streamlit as st
from psycopg.rows import dict_row


def normalize_database_url(db_url):
    parsed = urlsplit(db_url)

    if (parsed.username is None or parsed.password is None) and "@" in db_url:
        scheme, rest = db_url.split("://", 1)
        userinfo, hostinfo = rest.rsplit("@", 1)

        if ":" in userinfo:
            username, password = userinfo.split(":", 1)
        else:
            username, password = userinfo, ""

        username = quote(username or "", safe="")
        password = quote(password or "", safe="")

        return f"{scheme}://{username}:{password}@{hostinfo}"

    if parsed.username or parsed.password:
        username = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{host}{port}"

        return urlunsplit(
            (parsed.scheme, netloc, parsed.path or "", parsed.query or "", "")
        )

    return db_url


def get_database_url():
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        db_url = st.secrets.get("DATABASE_URL")

    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is missing. Add it to Streamlit secrets or the environment."
        )

    db_url = normalize_database_url(db_url)

    if "sslmode=" not in db_url:
        db_url = f"{db_url}?sslmode=require" if "?" not in db_url else f"{db_url}&sslmode=require"

    return db_url


def create_connection():
    return psycopg.connect(get_database_url(), row_factory=dict_row)


def create_tables():
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            entry TEXT NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    conn.commit()
    conn.close()
