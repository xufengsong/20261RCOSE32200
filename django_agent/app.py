import streamlit as st
import uuid
import difflib
import os
from langchain_core.messages import ToolMessage, HumanMessage
from graph import build_graph

# Setup layout
st.set_page_config(layout="wide", page_title="Antigravity IDE", initial_sidebar_state="expanded")

# Custom CSS for IDE-like appearance
st.markdown("""
<style>
    /* Hide top header and menu */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Remove padding around the main block */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 100%;
    }

    /* Style the columns to look like panes */
    [data-testid="column"] {
        border-right: 1px solid #2e3440;
        padding-right: 10px;
        padding-left: 10px;
        height: 95vh;
        overflow-y: auto;
    }
    
    /* Remove right border on the last column */
    [data-testid="column"]:last-child {
        border-right: none;
    }
    
    /* File tree button styling */
    .stButton>button {
        width: 100%;
        text-align: left;
        background-color: transparent;
        border: none;
        padding: 5px 10px;
    }
    .stButton>button:hover {
        background-color: #2e3440;
    }
</style>
""", unsafe_allow_html=True)

WORKSPACE_DIR = "my_django_project"

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.graph = build_graph()
    st.session_state.config = {"configurable": {"thread_id": st.session_state.thread_id}}
    st.session_state.messages = []
    st.session_state.processed_message_ids = set()
    st.session_state.active_file = None
    st.session_state.messages.append({"role": "assistant", "content": "Hello! I am your Django coding agent. What would you like me to build today?"})

def process_graph_stream(state_input=None):
    graph = st.session_state.graph
    config = st.session_state.config
    processed = st.session_state.processed_message_ids
    
    for event in graph.stream(state_input, config, stream_mode="values"):
        messages = event.get("messages", [])
        if not messages:
            continue
            
        last_msg = messages[-1]
        
        if getattr(last_msg, "id", None) in processed:
            continue
            
        if hasattr(last_msg, "id") and last_msg.id:
            processed.add(last_msg.id)
            
        if last_msg.type == "ai":
            if last_msg.content:
                st.session_state.messages.append({"role": "assistant", "content": last_msg.content})
        
        elif last_msg.type == "tool":
            pass

def list_files(startpath):
    # Returns a list of all files in the directory
    filepaths = []
    if os.path.exists(startpath):
        for root, dirs, files in os.walk(startpath):
            # Skip hidden dirs and venv
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', 'env', '__pycache__')]
            for f in files:
                if not f.startswith('.'):
                    filepaths.append(os.path.join(root, f))
    return filepaths

# 3 Columns: Explorer, Editor, Chat
col_exp, col_edit, col_chat = st.columns([1, 2, 1.5], gap="small")

with col_exp:
    st.markdown("### 📂 Explorer")
    files = list_files(WORKSPACE_DIR)
    if not files:
        st.caption("Workspace is empty or does not exist.")
    else:
        for f in files:
            # Display relative path for cleanliness
            rel_path = os.path.relpath(f, WORKSPACE_DIR)
            if st.button(f"📄 {rel_path}", key=f"btn_{f}"):
                st.session_state.active_file = f

with col_edit:
    st.markdown("### 💻 Editor")
    if st.session_state.active_file and os.path.exists(st.session_state.active_file):
        rel_path = os.path.relpath(st.session_state.active_file, WORKSPACE_DIR)
        st.markdown(f"**{rel_path}**")
        with open(st.session_state.active_file, "r", encoding="utf-8") as file:
            content = file.read()
            
        # Determine language for syntax highlighting
        ext = os.path.splitext(st.session_state.active_file)[1].lower()
        lang_map = {'.py': 'python', '.html': 'html', '.js': 'javascript', '.css': 'css', '.ts': 'typescript'}
        lang = lang_map.get(ext, 'markdown')
        
        st.code(content, language=lang)
    else:
        st.info("Select a file from the explorer to view its contents.")

with col_chat:
    st.markdown("### 💬 Agent")
    
    # Render messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Interrupt checks
    graph = st.session_state.graph
    config = st.session_state.config
    state = graph.get_state(config)
    
    needs_input = False
    
    if state.next and state.next[0] == "ask_permission":
        needs_input = True
        last_ai_msg = state.values["messages"][-1]
        
        for tc in last_ai_msg.tool_calls:
            if tc["name"] == "write_file" and "models.py" in tc["args"].get("filepath", ""):
                filepath = tc["args"].get("filepath", "")
                file_content = tc["args"].get("content", "")
                
                diff_text = ""
                if os.path.exists(filepath):
                    with open(filepath, "r", encoding="utf-8") as f:
                        old_content = f.read()
                    
                    diff = difflib.unified_diff(
                        old_content.splitlines(),
                        file_content.splitlines(),
                        fromfile=filepath,
                        tofile=filepath,
                        lineterm=""
                    )
                    diff_text = "\n".join(diff)
                else:
                    diff_text = f"File {filepath} does not exist. It will be created with the following content:\n{file_content}"
                
                if not diff_text.strip():
                    diff_text = "No changes detected."

                with st.chat_message("assistant"):
                    st.warning("⚠️ Action Required")
                    st.markdown(f"I need to modify **models.py**. Please review the proposed changes:\n\n```diff\n{diff_text}\n```")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("Approve"):
                            st.session_state.messages.append({"role": "user", "content": "✅ Changes approved! Resuming execution..."})
                            process_graph_stream(None)
                            st.rerun()
                    with col_b:
                        if st.button("Reject"):
                            st.session_state.messages.append({"role": "user", "content": "❌ Changes rejected! Injecting failure..."})
                            
                            tool_messages = []
                            for t in last_ai_msg.tool_calls:
                                if t["name"] == "write_file" and "models.py" in t["args"].get("filepath", ""):
                                    msg_content = "Error: User denied permission to modify models.py."
                                else:
                                    msg_content = "Error: Tool execution cancelled because models.py modification was denied."
                                
                                tool_messages.append(ToolMessage(
                                    tool_call_id=t["id"],
                                    name=t["name"],
                                    content=msg_content
                                ))
                            
                            graph.update_state(config, {"messages": tool_messages}, as_node="execute_tools")
                            process_graph_stream(None)
                            st.rerun()
                break

    # Accept user input only if we are not blocked
    if not needs_input:
        user_input = st.chat_input("Ask the agent...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            if not state.values:
                initial_state = {
                    "task": user_input,
                    "workspace_dir": WORKSPACE_DIR,
                    "messages": [],
                    "pending_tool_calls": [],
                    "tool_outputs": []
                }
                process_graph_stream(initial_state)
            else:
                graph.update_state(config, {"messages": [HumanMessage(content=user_input)]})
                process_graph_stream(None)
            
            st.rerun()
