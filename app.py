import streamlit as st
from utils.database import create_tables
from utils.auth import signup_user, login_user
from utils.logger import log_user_data, read_logs

st.title("Personal AI Assistant")

try:
    create_tables()
except Exception as exc:
    st.error(
        "Database startup failed. Check your DATABASE_URL and network access."
    )
    st.error(f"Details: {exc}")
    st.stop()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

menu = st.sidebar.selectbox(
    "Menu",
    ["Login", "Signup"]
)

# SIGNUP

if menu == "Signup":

    st.subheader("Create Account")

    new_user = st.text_input("Username")
    new_password = st.text_input(
        "Password",
        type="password"
    )

    if st.button("Signup"):

        if signup_user(new_user, new_password):
            st.success("Account created!")

        else:
            st.error("Username already exists.")

# LOGIN

elif menu == "Login":

    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button("Login"):

        if login_user(username, password):

            st.session_state.logged_in = True
            st.session_state.username = username

        else:
            st.error("fish")

# DASHBOARD

if st.session_state.logged_in:

    st.sidebar.success(
        f"Logged in as {st.session_state.username}"
    )

    st.header("User Dashboard")

    entry = st.text_area(
        "Log something (diet, notes, etc.)"
    )

    if st.button("Save Entry"):

        log_user_data(
            st.session_state.username,
            entry
        )

        st.success("Saved!")

    st.subheader("Your Logs")

    logs = read_logs(
        st.session_state.username
    )

    for log in logs:

        st.write(
            log["timestamp"],
            log["entry"]
        )
