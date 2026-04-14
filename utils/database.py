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
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT NOT NULL DEFAULT 'Chat',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Migration: if table exists with old schema, add conversation_id
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='logs' AND column_name='entry'
        """
    )
    if cursor.fetchone():
        cursor.execute("ALTER TABLE logs DROP COLUMN entry")
        cursor.execute("ALTER TABLE logs ADD COLUMN role TEXT DEFAULT 'user'")
        cursor.execute("ALTER TABLE logs ADD COLUMN content TEXT")

    # Add conversation_id column if missing
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='logs' AND column_name='conversation_id'
        """
    )
    if not cursor.fetchone():
        # Create default conversation for each user's existing messages
        cursor.execute(
            """
            INSERT INTO conversations (user_id, name, created_at)
            SELECT DISTINCT user_id, 'Chat', NOW()
            FROM logs
            ON CONFLICT DO NOTHING
            """
        )

        cursor.execute(
            """
            ALTER TABLE logs ADD COLUMN conversation_id INTEGER REFERENCES conversations(id)
            """
        )

        # Assign existing messages to default conversation
        cursor.execute(
            """
            UPDATE logs l SET conversation_id = c.id
            FROM conversations c
            WHERE l.user_id = c.user_id AND l.conversation_id IS NULL
            """
        )

        cursor.execute(
            "ALTER TABLE logs ALTER COLUMN conversation_id SET NOT NULL")

    conn.commit()
    conn.close()


def create_conversation(user_id, name="Chat"):
    """Create a new conversation for a user."""
    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO conversations (user_id, name) VALUES (%s, %s) RETURNING id",
                (user_id, name),
            )
            result = cursor.fetchone()
            conn.commit()

    return result["id"] if result else None


def get_user_conversations(user_id):
    """Get all conversations for a user."""
    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, created_at, updated_at
                FROM conversations
                WHERE user_id=%s
                ORDER BY updated_at DESC
                """,
                (user_id,),
            )
            return cursor.fetchall()


def update_conversation_name(conversation_id, new_name):
    """Update the name of a conversation."""
    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE conversations SET name=%s, updated_at=NOW() WHERE id=%s",
                (new_name, conversation_id),
            )
            conn.commit()


def get_user_id_from_username(username):
    """Get user ID from username."""
    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE username=%s",
                (username,),
            )
            result = cursor.fetchone()

    return result["id"] if result else None
