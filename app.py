from utils.database import create_tables
import streamlit as st
from openai import OpenAI
from streamlit_cookies_manager import CookieManager

from utils.database import (
    create_tables, get_user_conversations, create_conversation,
    update_conversation_name, get_user_id_from_username
)
from utils.auth import signup_user, login_user
from utils.logger import save_chat_message, get_chat_history
from utils.chat_utils import auto_rename_conversation

st.set_page_config(page_title="Personal AI Assistant", layout="wide")

# Initialize cookies safely
if "cookies" not in st.session_state:
    try:
        cookies_manager = CookieManager()
        if cookies_manager.ready():
            st.session_state.cookies = cookies_manager
        else:
            st.session_state.cookies = {}
    except Exception:
        st.session_state.cookies = {}

cookies = st.session_state.cookies

# Helper functions for cookie operations


def save_cookie(key, value):
    cookies[key] = value
    if hasattr(cookies, 'save'):
        cookies.save()


def delete_cookie(key):
    if key in cookies:
        del cookies[key]
    if hasattr(cookies, 'delete'):
        cookies.delete(key)
    if hasattr(cookies, 'save'):
        cookies.save()


def get_cookie(key, default=None):
    return cookies.get(key, default)


st.title("Personal AI Assistant")

try:
    create_tables()
except Exception as exc:
    st.error("Database startup failed. Check your DATABASE_URL and network access.")
    st.error(f"Details: {exc}")
    st.stop()

# Initialize session state
for key, default in {
    "logged_in": False,
    "just_logged_out": False,
    "current_conversation_id": None,
    "chat_history": [],
    "editing_conv": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Auto-login from cookies
if not st.session_state.logged_in and not st.session_state.just_logged_out:
    username_from_cookie = get_cookie("username")
    if username_from_cookie:
        st.session_state.logged_in = True
        st.session_state.username = username_from_cookie

if st.session_state.just_logged_out:
    st.session_state.just_logged_out = False

menu = st.sidebar.selectbox(
    "Menu", ["Login", "Signup"] if not st.session_state.logged_in else ["Chat"], key="main_menu")

# SIGNUP
if menu == "Signup":
    st.subheader("Create Account")
    new_user = st.text_input("Username")
    new_password = st.text_input("Password", type="password")

    if st.button("Signup"):
        if signup_user(new_user, new_password):
            st.success("Account created!")
        else:
            st.error("Username already exists.")

# LOGIN
elif menu == "Login":
    st.subheader("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")

        if submit_button:
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                save_cookie("username", username)
                st.rerun()
            else:
                st.error("Invalid username or password.")

# LOGOUT BUTTON
if st.session_state.logged_in:
    st.sidebar.divider()
    if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.current_conversation_id = None
        st.session_state.just_logged_out = True
        delete_cookie("username")
        st.rerun()

# CHATBOT DASHBOARD
if st.session_state.logged_in and menu == "Chat":
    st.sidebar.success(f"Logged in as {st.session_state.username}")

    user_id = get_user_id_from_username(st.session_state.username)
    st.sidebar.markdown("## Conversations")

    conversations = get_user_conversations(user_id)

    if st.sidebar.button("➕ New Chat", use_container_width=True):
        new_conv_id = create_conversation(user_id, "Chat")
        st.session_state.current_conversation_id = new_conv_id
        st.session_state.chat_history = []
        st.rerun()

    st.sidebar.divider()

    for conv in conversations:
        col1, col2 = st.sidebar.columns([4, 1])
        is_current = conv['id'] == st.session_state.current_conversation_id
        btn_text = f"✓ {conv['name']}" if is_current else conv['name']

        with col1:
            if st.button(btn_text, key=f"conv_{conv['id']}", use_container_width=True):
                st.session_state.current_conversation_id = conv['id']
                st.session_state.chat_history = get_chat_history(conv['id'])
                st.rerun()

        with col2:
            if st.button("✏️", key=f"edit_{conv['id']}", use_container_width=True):
                st.session_state.editing_conv = conv['id']

    # Handle conversation renaming
    if st.session_state.editing_conv:
        st.sidebar.divider()
        new_name = st.sidebar.text_input(
            "New chat name:", value="", key="new_conv_name")

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("Save", key="save_name"):
                if new_name.strip():
                    update_conversation_name(
                        st.session_state.editing_conv, new_name)
                    st.session_state.editing_conv = None
                    st.rerun()

        with col2:
            if st.button("Cancel", key="cancel_name"):
                st.session_state.editing_conv = None
                st.rerun()

    # Initialize first conversation if needed
    if not st.session_state.current_conversation_id and conversations:
        st.session_state.current_conversation_id = conversations[0]['id']
        st.session_state.chat_history = get_chat_history(
            conversations[0]['id'])
    elif not st.session_state.current_conversation_id:
        st.session_state.current_conversation_id = create_conversation(
            user_id, "Chat")
        st.rerun()

    st.header("Chat with AI")
    client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY"))

    if st.session_state.current_conversation_id:
        st.session_state.chat_history = get_chat_history(
            st.session_state.current_conversation_id)

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_input = st.chat_input("Type your message here...")

    if user_input and st.session_state.current_conversation_id:
        save_chat_message(st.session_state.username, "user",
                          user_input, st.session_state.current_conversation_id)
        st.session_state.chat_history.append(
            {"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            try:
                with st.spinner("Thinking..."):
                    response = client.chat.completions.create(
                        model="gpt-5-nano",
                        messages=[
                            {"role": msg["role"], "content": msg["content"]}
                            for msg in st.session_state.chat_history
                            if msg.get("role") and msg.get("content")
                        ],
                        stream=True,
                    )

                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.write(full_response)

            except Exception as e:
                st.error(f"Error: {str(e)}")
                full_response = f"Error: {str(e)}"

        save_chat_message(st.session_state.username, "assistant",
                          full_response, st.session_state.current_conversation_id)
        st.session_state.chat_history.append(
            {"role": "assistant", "content": full_response})

        auto_rename_conversation(
            st.session_state.current_conversation_id, st.session_state.username)
        st.rerun()


st.set_page_config(page_title="Personal AI Assistant", layout="wide")

# Initialize cookies safely
if "cookies" not in st.session_state:
    try:
        cookies_manager = CookieManager()
        if cookies_manager.ready():
            st.session_state.cookies = cookies_manager
        else:
            st.session_state.cookies = {}
    except Exception:
        st.session_state.cookies = {}

cookies = st.session_state.cookies

# Helper functions for cookie operations


def save_cookie(key, value):
    cookies[key] = value
    if hasattr(cookies, 'save'):
        cookies.save()


def delete_cookie(key):
    if key in cookies:
        del cookies[key]
    if hasattr(cookies, 'delete'):
        cookies.delete(key)
    if hasattr(cookies, 'save'):
        cookies.save()


def get_cookie(key, default=None):
    return cookies.get(key, default)


st.title("Personal AI Assistant")

try:
    create_tables()
except Exception as exc:
    st.error("Database startup failed. Check your DATABASE_URL and network access.")
    st.error(f"Details: {exc}")
    st.stop()

# Initialize session state
for key, default in {
    "logged_in": False,
    "just_logged_out": False,
    "current_conversation_id": None,
    "chat_history": [],
    "editing_conv": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Auto-login from cookies
if not st.session_state.logged_in and not st.session_state.just_logged_out:
    username_from_cookie = get_cookie("username")
    if username_from_cookie:
        st.session_state.logged_in = True
        st.session_state.username = username_from_cookie

if st.session_state.just_logged_out:
    st.session_state.just_logged_out = False

menu = st.sidebar.selectbox(
    "Menu", ["Login", "Signup"] if not st.session_state.logged_in else ["Chat"], key="main_menu")

# SIGNUP
if menu == "Signup":
    st.subheader("Create Account")
    new_user = st.text_input("Username")
    new_password = st.text_input("Password", type="password")

    if st.button("Signup"):
        if signup_user(new_user, new_password):
            st.success("Account created!")
        else:
            st.error("Username already exists.")

# LOGIN
elif menu == "Login":
    st.subheader("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")

        if submit_button:
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                save_cookie("username", username)
                st.rerun()
            else:
                st.error("Invalid username or password.")

# LOGOUT BUTTON
if st.session_state.logged_in:
    st.sidebar.divider()
    if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.current_conversation_id = None
        st.session_state.just_logged_out = True
        delete_cookie("username")
        st.rerun()

# CHATBOT DASHBOARD
if st.session_state.logged_in and menu == "Chat":
    st.sidebar.success(f"Logged in as {st.session_state.username}")

    user_id = get_user_id_from_username(st.session_state.username)
    st.sidebar.markdown("## Conversations")

    conversations = get_user_conversations(user_id)

    if st.sidebar.button("➕ New Chat", use_container_width=True):
        new_conv_id = create_conversation(user_id, "Chat")
        st.session_state.current_conversation_id = new_conv_id
        st.session_state.chat_history = []
        st.rerun()

    st.sidebar.divider()

    for conv in conversations:
        col1, col2 = st.sidebar.columns([4, 1])
        is_current = conv['id'] == st.session_state.current_conversation_id
        btn_text = f"✓ {conv['name']}" if is_current else conv['name']

        with col1:
            if st.button(btn_text, key=f"conv_{conv['id']}", use_container_width=True):
                st.session_state.current_conversation_id = conv['id']
                st.session_state.chat_history = get_chat_history(conv['id'])
                st.rerun()

        with col2:
            if st.button("✏️", key=f"edit_{conv['id']}", use_container_width=True):
                st.session_state.editing_conv = conv['id']

    # Handle conversation renaming
    if st.session_state.editing_conv:
        st.sidebar.divider()
        new_name = st.sidebar.text_input(
            "New chat name:", value="", key="new_conv_name")

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("Save", key="save_name"):
                if new_name.strip():
                    update_conversation_name(
                        st.session_state.editing_conv, new_name)
                    st.session_state.editing_conv = None
                    st.rerun()

        with col2:
            if st.button("Cancel", key="cancel_name"):
                st.session_state.editing_conv = None
                st.rerun()

    # Initialize first conversation if needed
    if not st.session_state.current_conversation_id and conversations:
        st.session_state.current_conversation_id = conversations[0]['id']
        st.session_state.chat_history = get_chat_history(
            conversations[0]['id'])
    elif not st.session_state.current_conversation_id:
        st.session_state.current_conversation_id = create_conversation(
            user_id, "Chat")
        st.rerun()

    st.header("Chat with AI")
    client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY"))

    if st.session_state.current_conversation_id:
        st.session_state.chat_history = get_chat_history(
            st.session_state.current_conversation_id)

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_input = st.chat_input("Type your message here...")

    if user_input and st.session_state.current_conversation_id:
        save_chat_message(st.session_state.username, "user",
                          user_input, st.session_state.current_conversation_id)
        st.session_state.chat_history.append(
            {"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            try:
                with st.spinner("Thinking..."):
                    response = client.chat.completions.create(
                        model="gpt-5-nano",
                        messages=[
                            {"role": msg["role"], "content": msg["content"]}
                            for msg in st.session_state.chat_history
                            if msg.get("role") and msg.get("content")
                        ],
                        stream=True,
                    )

                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.write(full_response)

            except Exception as e:
                st.error(f"Error: {str(e)}")
                full_response = f"Error: {str(e)}"

        save_chat_message(st.session_state.username, "assistant",
                          full_response, st.session_state.current_conversation_id)
        st.session_state.chat_history.append(
            {"role": "assistant", "content": full_response})

        auto_rename_conversation(
            st.session_state.current_conversation_id, st.session_state.username)
        st.rerun()


st.set_page_config(page_title="Personal AI Assistant", layout="wide")

# Initialize cookies (store in session state to avoid duplicates)
if "cookies" not in st.session_state:
    try:
        cookies_manager = CookieManager()
        if cookies_manager.ready():
            st.session_state.cookies = cookies_manager
        else:
            # If cookies not ready, create a fallback dict
            st.session_state.cookies = {}
    except Exception as e:
        st.session_state.cookies = {}

cookies = st.session_state.cookies

st.title("Personal AI Assistant")

# Helper function for cookie operations


def save_cookie(key, value):
    cookies[key] = value
    if hasattr(cookies, 'save'):
        cookies.save()


def delete_cookie(key):
    if key in cookies:
        del cookies[key]
    if hasattr(cookies, 'delete'):
        cookies.delete(key)
    if hasattr(cookies, 'save'):
        cookies.save()


def get_cookie(key, default=None):
    return cookies.get(key, default)


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

if "just_logged_out" not in st.session_state:
    st.session_state.just_logged_out = False

if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "editing_conv" not in st.session_state:
    st.session_state.editing_conv = None

# Check for existing login via cookies (but not if we just logged out)
if not st.session_state.logged_in and not st.session_state.just_logged_out and "username" in cookies:
    st.session_state.logged_in = True
    st.session_state.username = cookies["username"]

# Reset the just_logged_out flag after checking
if st.session_state.just_logged_out:
    st.session_state.just_logged_out = False

menu = st.sidebar.selectbox(
    "Menu", ["Login", "Signup"] if not st.session_state.logged_in else ["Chat"])

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

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input(
            "Password",
            type="password"
        )
        submit_button = st.form_submit_button("Login")

        if submit_button:
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                cookies["username"] = username
                cookies.save()
                st.rerun()
            else:
                st.error("Invalid username or password.")

# LOGOUT BUTTON (always visible when logged in)
if st.session_state.logged_in:
    st.sidebar.divider()
    if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.current_conversation_id = None
        st.session_state.just_logged_out = True
        delete_cookie("username")
        st.rerun()

# CHATBOT DASHBOARD

if st.session_state.logged_in and menu == "Chat":

    st.sidebar.success(f"Logged in as {st.session_state.username}")

    # Get user ID
    user_id = get_user_id_from_username(st.session_state.username)

    st.sidebar.markdown("## Conversations")

    # List conversations
    conversations = get_user_conversations(user_id)

    # Create new chat button
    if st.sidebar.button("➕ New Chat", use_container_width=True):
        new_conv_id = create_conversation(user_id, "Chat")
        st.session_state.current_conversation_id = new_conv_id
        st.session_state.chat_history = []
        st.rerun()

    st.sidebar.divider()

    # Display conversation list
    for conv in conversations:
        col1, col2 = st.sidebar.columns([4, 1])

        is_current = conv['id'] == st.session_state.current_conversation_id
        btn_text = f"✓ {conv['name']}" if is_current else conv['name']

        with col1:
            if st.button(btn_text, key=f"conv_{conv['id']}", use_container_width=True):
                st.session_state.current_conversation_id = conv['id']
                st.session_state.chat_history = get_chat_history(conv['id'])
                st.rerun()

        with col2:
            if st.button("✏️", key=f"edit_{conv['id']}", use_container_width=True):
                st.session_state.editing_conv = conv['id']

    # Handle conversation renaming
    if st.session_state.editing_conv:
        st.sidebar.divider()
        new_name = st.sidebar.text_input(
            "New chat name:", value="", key="new_conv_name")

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("Save", key="save_name"):
                if new_name.strip():
                    update_conversation_name(
                        st.session_state.editing_conv, new_name)
                    st.session_state.editing_conv = None
                    st.rerun()

        with col2:
            if st.button("Cancel", key="cancel_name"):
                st.session_state.editing_conv = None
                st.rerun()

    # Initialize first conversation if none exists
    if not st.session_state.current_conversation_id and conversations:
        st.session_state.current_conversation_id = conversations[0]['id']
        st.session_state.chat_history = get_chat_history(
            conversations[0]['id'])
    elif not st.session_state.current_conversation_id:
        st.session_state.current_conversation_id = create_conversation(
            user_id, "Chat")
        st.rerun()

    st.header("Chat with AI")

    # Initialize OpenAI client
    client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY"))

    # Re-load chat history if conversation changed
    if st.session_state.current_conversation_id:
        st.session_state.chat_history = get_chat_history(
            st.session_state.current_conversation_id)

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Chat input
    user_input = st.chat_input("Type your message here...")

    if user_input and st.session_state.current_conversation_id:
        # Add user message to history
        save_chat_message(st.session_state.username, "user",
                          user_input, st.session_state.current_conversation_id)
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input
        })

        # Display user message
        with st.chat_message("user"):
            st.write(user_input)

        # Get AI response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            try:
                with st.spinner("Thinking..."):
                    response = client.chat.completions.create(
                        model="gpt-5-nano",
                        messages=[
                            {"role": msg["role"],
                                "content": msg["content"]}
                            for msg in st.session_state.chat_history
                            if msg.get("role") and msg.get("content")
                        ],
                        stream=True,
                    )

                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.write(full_response)

            except Exception as e:
                st.error(f"Error: {str(e)}")
                full_response = f"Error: {str(e)}"

        # Save assistant response
        save_chat_message(st.session_state.username,
                          "assistant", full_response, st.session_state.current_conversation_id)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": full_response
        })

        # Try to auto-rename the conversation
        auto_rename_conversation(
            st.session_state.current_conversation_id, st.session_state.username)
        st.rerun()


st.set_page_config(page_title="Personal AI Assistant", layout="wide")

# Initialize cookies
cookies = CookieManager()
if not cookies.ready():
    st.stop()

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

if "just_logged_out" not in st.session_state:
    st.session_state.just_logged_out = False

# Check for existing login via cookies (but not if we just logged out)
if not st.session_state.logged_in and not st.session_state.just_logged_out and "username" in cookies:
    st.session_state.logged_in = True
    st.session_state.username = cookies["username"]

# Reset the just_logged_out flag after checking
if st.session_state.just_logged_out:
    st.session_state.just_logged_out = False

menu = st.sidebar.selectbox(
    "Menu", ["Login", "Signup"] if not st.session_state.logged_in else ["Chat"])

# LOGOUT BUTTON (always visible when logged in)
if st.session_state.logged_in:
    st.sidebar.divider()
    if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.just_logged_out = True
        cookies.delete("username")
        cookies.save()
        st.rerun()

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

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input(
            "Password",
            type="password"
        )
        submit_button = st.form_submit_button("Login")

        if submit_button:
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                cookies["username"] = username
                cookies.save()
                st.rerun()
            else:
                st.error("Invalid username or password.")

# LOGOUT

elif menu == "Logout":
    if st.sidebar.button("Confirm Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        cookies.delete("username")
        st.rerun()

# CHATBOT DASHBOARD

if st.session_state.logged_in:

    st.sidebar.success(f"Logged in as {st.session_state.username}")

    st.header("Chat with AI")

    # Initialize OpenAI client
    client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY"))

    # Initialize chat history in session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = get_chat_history(
            st.session_state.username)

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Chat input
    user_input = st.chat_input("Type your message here...")

    if user_input:
        # Add user message to history
        save_chat_message(st.session_state.username, "user", user_input)
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input
        })

        # Display user message
        with st.chat_message("user"):
            st.write(user_input)

        # Get AI response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            try:
                with st.spinner("Thinking..."):
                    response = client.chat.completions.create(
                        model="gpt-5-nano",
                        messages=[
                            {"role": msg["role"],
                                "content": msg["content"]}
                            for msg in st.session_state.chat_history
                            if msg.get("role") and msg.get("content")
                        ],
                        stream=True,
                    )

                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.write(full_response)

            except Exception as e:
                st.error(f"Error: {str(e)}")
                full_response = f"Error: {str(e)}"

        # Save assistant response
        save_chat_message(st.session_state.username,
                          "assistant", full_response)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": full_response
        })

        st.rerun()
