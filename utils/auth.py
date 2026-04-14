import bcrypt
from psycopg.errors import UniqueViolation

from utils.database import create_connection


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())


def signup_user(username, password):
    hashed_pw = hash_password(password)

    try:
        with create_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (username, password) VALUES (%s, %s)",
                    (username, hashed_pw),
                )
            conn.commit()

        return True

    except UniqueViolation:
        return False


def login_user(username, password):
    with create_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT password FROM users WHERE username=%s",
                (username,),
            )
            result = cursor.fetchone()

    if result:
        stored_pw = result["password"]

        if verify_password(password, stored_pw):
            return True

    return False
