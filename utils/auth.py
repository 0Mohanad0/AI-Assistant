import bcrypt
import sqlite3
from utils.database import create_connection


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())


def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)


def signup_user(username, password):
    conn = create_connection()
    cursor = conn.cursor()

    hashed_pw = hash_password(password)

    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed_pw)
        )

        conn.commit()

        # Create user folder
        import os
        os.makedirs(f"users/{username}", exist_ok=True)

        return True

    except:
        return False

    finally:
        conn.close()


def login_user(username, password):
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT password FROM users WHERE username=?",
        (username,)
    )

    result = cursor.fetchone()

    conn.close()

    if result:
        stored_pw = result[0]

        if verify_password(password, stored_pw):
            return True

    return False
