from utils.database import create_connection


def _get_user_id(username):
    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE username=%s",
                (username,),
            )
            result = cursor.fetchone()

    if result:
        return result["id"]

    return None


def save_chat_message(username, role, content, conversation_id):
    """Save a chat message to a specific conversation."""
    user_id = _get_user_id(username)
    if user_id is None or conversation_id is None:
        return False

    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO logs (user_id, conversation_id, role, content) VALUES (%s, %s, %s, %s)",
                (user_id, conversation_id, role, content),
            )
            # Update conversation's updated_at timestamp
            cursor.execute(
                "UPDATE conversations SET updated_at=NOW() WHERE id=%s",
                (conversation_id,),
            )
            conn.commit()

    return True


def get_chat_history(conversation_id):
    """Retrieve all chat messages in a conversation."""
    if conversation_id is None:
        return []

    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT role, content, timestamp
                FROM logs
                WHERE conversation_id=%s AND role IS NOT NULL AND content IS NOT NULL
                ORDER BY timestamp ASC
                """,
                (conversation_id,),
            )
            messages = cursor.fetchall()
            return [msg for msg in messages if msg.get("role") and msg.get("content")]


def log_user_data(username, entry, conversation_id):
    return save_chat_message(username, "user", entry, conversation_id)


def read_logs(conversation_id):
    return get_chat_history(conversation_id)


def get_conversation_message_count(conversation_id):
    """Get number of messages in a conversation."""
    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as count FROM logs WHERE conversation_id=%s",
                (conversation_id,),
            )
            result = cursor.fetchone()

    return result["count"] if result else 0
