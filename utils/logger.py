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


def log_user_data(username, entry):
    user_id = _get_user_id(username)
    if user_id is None:
        return False

    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO logs (user_id, entry) VALUES (%s, %s)",
                (user_id, entry),
            )
        conn.commit()

    return True


def read_logs(username):
    user_id = _get_user_id(username)
    if user_id is None:
        return []

    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT timestamp, entry
                FROM logs
                WHERE user_id=%s
                ORDER BY timestamp DESC
                """,
                (user_id,),
            )
            return cursor.fetchall()
