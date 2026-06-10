import streamlit as st
import uuid
import difflib
import os
from langchain_core.messages import ToolMessage, HumanMessage
from graph import build_graph

st.set_page_config(layout="wide", page_title="Django Agent Workspace")

WORKSPACE_DIR = "my_django_project"

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.graph = build_graph()
    st.session_state.config = {"configurable": {"thread_id": st.session_state.thread_id}}
    st.session_state.messages = []
    st.session_state.processed_message_ids = set()
    st.session_state.messages.append({"role": "assistant", "content": "Hello! I am your Django coding agent. What would you like me to build today?"})

def process_graph_stream(state_input=None):
    graph = st.session_state.graph
    config = st.session_state.config
    processed = st.session_state.processed_message_ids
    
    # We use stream instead of astream for Streamlit sync flow
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
            # Optional: log tools or add them to messages if you want them visible
            pass

main_col, sidebar_col = st.columns([3, 1], gap="large")

with main_col:
    st.title("Workspace & File Management")
    st.markdown("Import folders or files to your workspace to begin.")
    uploaded_files = st.file_uploader("Upload Files / Folders", accept_multiple_files=True)
    if uploaded_files:
        st.success(f"{len(uploaded_files)} files uploaded successfully (Simulation).")

    st.markdown("### Current Workspace")
    st.code(f"{WORKSPACE_DIR}/\n├── models.py\n├── views.py\n├── urls.py\n└── ...", language="bash")

with sidebar_col:
    st.header("Agent Chat")
    
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
        user_input = st.chat_input("What would you like me to build today?")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            # Immediate redraw to show user's message
            # But wait, we can just process and rerun
            
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
