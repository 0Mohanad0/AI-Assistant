from openai import OpenAI
import streamlit as st
from utils.logger import get_chat_history, get_conversation_message_count
from utils.database import update_conversation_name


def should_auto_rename(conversation_id):
    """Check if conversation should be auto-renamed (needs 4+ messages)."""
    if conversation_id is None:
        return False

    count = get_conversation_message_count(conversation_id)
    return count >= 4


def auto_rename_conversation(conversation_id, username):
    """Generate and set a new name for the conversation based on its content."""
    if not should_auto_rename(conversation_id):
        return False

    try:
        history = get_chat_history(conversation_id)
        if len(history) < 2:
            return False

        # Get first few messages for context
        preview = " ".join([msg.get("content", "")[:100]
                           for msg in history[:3]])

        client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {
                    "role": "system",
                    "content": "Generate a short, catchy title (3-5 words) for a chat conversation. Only return the title, nothing else."
                },
                {
                    "role": "user",
                    "content": f"Chat preview: {preview}"
                }
            ],
            max_tokens=20,
        )

        new_name = response.choices[0].message.content.strip()

        # Ensure name isn't too long
        if len(new_name) > 50:
            new_name = new_name[:47] + "..."

        update_conversation_name(conversation_id, new_name)
        return True

    except Exception as e:
        st.warning(f"Could not auto-rename chat: {str(e)}")
        return False
