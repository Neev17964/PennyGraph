import streamlit as st
from backend import chatbot, retrieve_all_threads, delete_thread, delete_all_threads
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import uuid

st.set_page_config(page_title="LangGraph Chatbot", page_icon="💬", layout="wide")

# =========================== User Identity ===========================
# NOTE: This is a lightweight, non-secure way to scope chats per user.
# It's enough to stop one visitor's "Delete All Chats" from wiping out
# everyone else's threads, but it is NOT authentication — anyone who
# types the same username gets access to that username's chats.
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None

if not st.session_state["user_id"]:
    st.markdown("""
    <style>
        #MainMenu, footer, header {visibility: hidden;}
        .stApp {
            background: radial-gradient(circle at top left, #14162b 0%, #0a0b14 60%);
        }
        div[data-testid="stForm"] {
            max-width: 420px;
            margin: 8vh auto 0 auto;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            padding: 2.6rem 2.4rem 2rem 2.4rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.35);
        }
        .login-icon { font-size: 2.6rem; text-align: center; margin-bottom: 0.4rem; }
        .login-title {
            text-align: center;
            font-size: 1.7rem;
            font-weight: 800;
            background: linear-gradient(90deg, #8b5cf6, #ec4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.3rem;
        }
        .login-subtitle {
            text-align: center;
            color: rgba(255,255,255,0.5);
            font-size: 0.92rem;
            margin-bottom: 1.6rem;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input {
            border-radius: 10px !important;
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            color: white !important;
            padding: 0.65rem 0.9rem !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input:focus {
            border-color: rgba(139, 92, 246, 0.6) !important;
            box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
        }
        div[data-testid="stForm"] button {
            width: 100%;
            background: linear-gradient(90deg, #7c3aed, #d946ef) !important;
            border: none !important;
            color: white !important;
            font-weight: 600 !important;
            border-radius: 10px !important;
            padding: 0.6rem 0 !important;
            margin-top: 0.6rem;
            transition: filter 0.15s ease;
        }
        div[data-testid="stForm"] button:hover {
            filter: brightness(1.12);
        }
        .login-footnote {
            margin-top: 1.2rem;
            text-align: center;
            font-size: 0.75rem;
            color: rgba(255,255,255,0.3);
        }
    </style>
    """, unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        st.markdown('<div class="login-icon">💬</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">LangGraph Chatbot</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">Enter a username to start chatting</div>', unsafe_allow_html=True)

        username = st.text_input(
            "username",
            placeholder="e.g. arjun123",
            label_visibility="collapsed",
        )
        continue_clicked = st.form_submit_button("Continue →", type="primary")
        st.markdown(
            '<div class="login-footnote">This is not secure authentication — '
            'it just keeps your chats separate from others.</div>',
            unsafe_allow_html=True,
        )

    if continue_clicked:
        if username.strip():
            st.session_state["user_id"] = username.strip()
            st.rerun()
        else:
            st.warning("Please enter a username.")
    st.stop()

USER_ID = st.session_state["user_id"]

# =========================== Custom Styling ===========================
st.markdown("""
<style>
    /* ---- General ---- */
    #MainMenu, footer, header {visibility: hidden;}
    .stApp {
        background: radial-gradient(circle at top left, #14162b 0%, #0a0b14 60%);
    }

    /* ---- Sidebar ---- */
    section[data-testid="stSidebar"] {
        background: #12131f;
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.2rem;
    }

    .sidebar-title {
        font-size: 1.35rem;
        font-weight: 700;
        background: linear-gradient(90deg, #8b5cf6, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1.2rem;
        letter-spacing: 0.3px;
    }

    .section-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: rgba(255,255,255,0.4);
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin: 1.4rem 0 0.5rem 0;
    }

    /* New Chat button — primary accent */
    div[data-testid="stSidebar"] button[kind="primary"] {
        background: linear-gradient(90deg, #7c3aed, #d946ef);
        border: none;
        color: white;
        font-weight: 600;
        border-radius: 10px;
    }
    div[data-testid="stSidebar"] button[kind="primary"]:hover {
        filter: brightness(1.1);
    }

    /* Secondary sidebar buttons (Delete All, chat items, menu) */
    div[data-testid="stSidebar"] button {
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.03);
        color: rgba(255,255,255,0.85);
        transition: all 0.15s ease;
    }
    div[data-testid="stSidebar"] button:hover {
        background: rgba(139, 92, 246, 0.15);
        border-color: rgba(139, 92, 246, 0.4);
        color: white;
    }

    /* Active chat highlight */
    .active-chat button {
        background: rgba(139, 92, 246, 0.22) !important;
        border-color: rgba(139, 92, 246, 0.55) !important;
        color: white !important;
        font-weight: 600;
    }

    /* Chat row spacing */
    div[data-testid="stSidebar"] .stHorizontalBlock {
        gap: 0.3rem;
        margin-bottom: 0.3rem;
    }

    /* Popover trigger (the ⋮ button) — make it compact */
    div[data-testid="stPopover"] button {
        padding: 0.25rem 0.5rem !important;
        min-height: 2.4rem;
    }

    /* Chat message bubbles */
    div[data-testid="stChatMessage"] {
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 14px;
        padding: 0.6rem 1rem;
        margin-bottom: 0.6rem;
    }

    /* Chat input */
    div[data-testid="stChatInput"] textarea {
        border-radius: 12px;
    }

    /* Empty state */
    .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 60vh;
        opacity: 0.55;
        text-align: center;
    }
    .empty-state h2 {
        font-weight: 700;
        background: linear-gradient(90deg, #8b5cf6, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


# =========================== Utilities ===========================
def generate_thread_id():
    return str(uuid.uuid4())


def get_next_chat_name():
    used_numbers = []
    for thread_id in st.session_state.get("chat_threads", []):
        current_name = st.session_state.get("chat_names", {}).get(thread_id, "")
        if current_name.lower().startswith("chat"):
            suffix = current_name[4:]
            if suffix.isdigit():
                used_numbers.append(int(suffix))

    candidate = 1
    while candidate in used_numbers:
        candidate += 1
    return f"chat{candidate}"


def reset_chat():
    thread_id = generate_thread_id()
    st.session_state["thread_id"] = thread_id
    add_thread(thread_id)
    st.session_state["message_history"] = []


def add_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)

    if thread_id not in st.session_state.get("chat_names", {}):
        st.session_state["chat_names"][thread_id] = get_next_chat_name()


def refresh_chat_threads():
    st.session_state["chat_threads"] = retrieve_all_threads(USER_ID)


def load_conversation(thread_id):
    state = chatbot.get_state(config={"configurable": {"thread_id": thread_id}})
    return state.values.get("messages", [])


def build_display_history(raw_messages):
    """
    Convert raw LangGraph messages into chat bubbles.
    - HumanMessage -> user bubble
    - ToolMessage  -> NOT a bubble; attached as metadata to the next real AI answer
    - AIMessage with empty content (a tool-call request) -> skipped
    - AIMessage with real content -> assistant bubble, carrying any tool calls
      that led up to it (shown via an expander, not as raw text)
    """
    display = []
    pending_tools = []

    for msg in raw_messages:
        if isinstance(msg, HumanMessage):
            display.append({"role": "user", "content": msg.content, "tools": None})

        elif isinstance(msg, ToolMessage):
            pending_tools.append({
                "name": getattr(msg, "name", "tool"),
                "output": msg.content,
            })

        elif isinstance(msg, AIMessage):
            if msg.content:  # skip empty tool-call-only messages
                display.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tools": pending_tools or None,
                })
                pending_tools = []

    return display


def open_thread(thread_id):
    st.session_state["thread_id"] = thread_id
    raw_messages = load_conversation(thread_id)
    st.session_state["message_history"] = build_display_history(raw_messages)


def delete_selected_thread(thread_id):
    delete_thread(thread_id)
    refresh_chat_threads()

    if thread_id in st.session_state.get("chat_names", {}):
        del st.session_state["chat_names"][thread_id]

    if st.session_state.get("thread_id") == thread_id:
        if st.session_state["chat_threads"]:
            st.session_state["thread_id"] = st.session_state["chat_threads"][-1]
        else:
            st.session_state["thread_id"] = None
        st.session_state["message_history"] = []


# ======================= Session Initialization ===================
# If the logged-in identity changed since the last run (e.g. someone logged
# out and a different account logged back in within the same browser
# session), wipe all user-scoped state so nothing from the previous
# account lingers until a manual refresh.
if st.session_state.get("_active_user_id") != USER_ID:
    st.session_state["_active_user_id"] = USER_ID
    st.session_state["message_history"] = []
    st.session_state["thread_id"] = None
    st.session_state["chat_threads"] = retrieve_all_threads(USER_ID)
    st.session_state["chat_names"] = {}

if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = None

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = retrieve_all_threads(USER_ID)

if "chat_names" not in st.session_state:
    st.session_state["chat_names"] = {}

for thread_id in st.session_state["chat_threads"]:
    if thread_id not in st.session_state["chat_names"]:
        st.session_state["chat_names"][thread_id] = get_next_chat_name()

# ============================ Sidebar ============================
with st.sidebar:
    st.markdown('<div class="sidebar-title">💬 LangGraph Chatbot</div>', unsafe_allow_html=True)
    st.caption(f"👤 Signed in as **{USER_ID}**")
    if st.button("Switch user", use_container_width=True):
        st.session_state["user_id"] = None
        st.session_state["thread_id"] = None
        st.session_state["message_history"] = []
        st.session_state["chat_threads"] = []
        st.session_state["chat_names"] = {}
        st.session_state["_active_user_id"] = None
        st.rerun()

    if st.button("➕  New Chat", use_container_width=True, type="primary"):
        reset_chat()
        st.rerun()

    if st.button("🗑️  Delete All Chats", use_container_width=True):
        delete_all_threads(USER_ID)
        refresh_chat_threads()
        st.session_state["thread_id"] = None
        st.session_state["message_history"] = []
        st.session_state["chat_names"] = {}
        st.rerun()

    st.markdown('<div class="section-label">My Conversations</div>', unsafe_allow_html=True)

    if not st.session_state["chat_threads"]:
        st.caption("No chats yet — start a new one!")
    else:
        for thread_id in st.session_state["chat_threads"][::-1]:
            chat_name = st.session_state["chat_names"].get(thread_id, "chat1")
            is_active = st.session_state.get("thread_id") == thread_id

            row_wrapper = st.container()
            with row_wrapper:
                if is_active:
                    st.markdown('<div class="active-chat">', unsafe_allow_html=True)

                col_name, col_menu = st.columns([5, 1])

                with col_name:
                    icon = "🟣" if is_active else "💭"
                    if st.button(
                        f"{icon}  {chat_name}",
                        key=f"thread_{thread_id}",
                        use_container_width=True,
                    ):
                        open_thread(thread_id)
                        st.rerun()

                with col_menu:
                    with st.popover("⋮", use_container_width=True):
                        st.markdown(f"**{chat_name}**")

                        new_name = st.text_input(
                            "Rename",
                            value=chat_name,
                            key=f"rename_input_{thread_id}",
                            label_visibility="collapsed",
                            placeholder="New name…",
                        )
                        if st.button("✏️ Save name", key=f"rename_btn_{thread_id}", use_container_width=True):
                            if new_name.strip():
                                st.session_state["chat_names"][thread_id] = new_name.strip()
                                st.rerun()

                        st.divider()

                        if st.button("🗑️ Delete chat", key=f"delete_{thread_id}", use_container_width=True):
                            delete_selected_thread(thread_id)
                            st.rerun()

                if is_active:
                    st.markdown('</div>', unsafe_allow_html=True)

# ============================ Main UI ============================

if not st.session_state["message_history"] and not st.session_state.get("thread_id"):
    st.markdown("""
    <div class="empty-state">
        <h2>Start a conversation</h2>
        <p>Ask me anything — I can search the web, check stock prices, and do quick math.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    for message in st.session_state["message_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("tools"):
                with st.expander("🔧 Tools used"):
                    for t in message["tools"]:
                        st.markdown(f"**{t['name']}**")
                        st.code(t["output"], language="json")

user_input = st.chat_input("Type here")

if user_input:
    if not st.session_state.get("thread_id"):
        reset_chat()

    st.session_state["message_history"].append(
        {"role": "user", "content": user_input, "tools": None}
    )
    with st.chat_message("user"):
        st.markdown(user_input)

    CONFIG = {
        "configurable": {"thread_id": st.session_state["thread_id"]},
        "metadata": {"thread_id": st.session_state["thread_id"], "user_id": USER_ID},
        "run_name": "chat_turn",
    }

    with st.chat_message("assistant"):
        status_holder = {"box": None}
        used_tools = []  # collected so we can attach them to the saved message

        def ai_only_stream():
            for message_chunk, metadata in chatbot.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode="messages",
            ):
                if isinstance(message_chunk, ToolMessage):
                    tool_name = getattr(message_chunk, "name", "tool")
                    used_tools.append({"name": tool_name, "output": message_chunk.content})

                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(
                            f"🔧 Using `{tool_name}` …", expanded=True
                        )
                    else:
                        status_holder["box"].update(
                            label=f"🔧 Using `{tool_name}` …",
                            state="running",
                            expanded=True,
                        )

                # Only stream real natural-language content, never raw tool output
                if isinstance(message_chunk, AIMessage) and message_chunk.content:
                    yield message_chunk.content

        ai_message = st.write_stream(ai_only_stream())

        if status_holder["box"] is not None:
            status_holder["box"].update(
                label="✅ Tool finished", state="complete", expanded=False
            )
            with st.expander("🔧 Tools used"):
                for t in used_tools:
                    st.markdown(f"**{t['name']}**")
                    st.code(t["output"], language="json")

    st.session_state["message_history"].append(
        {"role": "assistant", "content": ai_message, "tools": used_tools or None}
    )