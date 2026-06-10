import chainlit as cl
import uuid
from langchain_core.messages import ToolMessage, HumanMessage
from graph import build_graph

WORKSPACE_DIR = "my_django_project"

@cl.on_chat_start
async def on_chat_start():
    graph = build_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    cl.user_session.set("graph", graph)
    cl.user_session.set("config", config)
    cl.user_session.set("processed_message_ids", set())
    
    await cl.Message("Hello! I am your Django coding agent. What would you like me to build today?").send()

async def process_graph_stream(graph, state_input, config):
    processed_message_ids = cl.user_session.get("processed_message_ids")
    
    async for event in graph.astream(state_input, config, stream_mode="values"):
        messages = event.get("messages", [])
        if not messages:
            continue
            
        last_msg = messages[-1]
        
        # We use message id to avoid printing the same message twice in stream_mode="values"
        if getattr(last_msg, "id", None) in processed_message_ids:
            continue
            
        if hasattr(last_msg, "id") and last_msg.id:
            processed_message_ids.add(last_msg.id)
            
        if last_msg.type == "ai":
            if last_msg.content:
                await cl.Message(content=last_msg.content, author="Agent").send()
            
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                for tool_call in last_msg.tool_calls:
                    async with cl.Step(name=tool_call["name"]) as step:
                        step.input = tool_call["args"]
                        # We don't have the output yet, it will be in the next state.
                        
        elif last_msg.type == "tool":
            async with cl.Step(name=last_msg.name) as step:
                step.output = last_msg.content

    # Check for human-in-the-loop interruptions
    state = graph.get_state(config)
    if state.next and state.next[0] == "ask_permission":
        last_ai_msg = state.values["messages"][-1]
        
        for tc in last_ai_msg.tool_calls:
            if tc["name"] == "write_file" and "models.py" in tc["args"].get("filepath", ""):
                file_content = tc["args"].get("content", "")
                
                # Create action buttons
                actions = [
                    cl.Action(name="approve_changes", value="approve", description="Approve", label="Approve"),
                    cl.Action(name="approve_changes", value="reject", description="Reject", label="Reject")
                ]
                
                msg = cl.Message(
                    content=f"⚠️ **Action Required** ⚠️\n\nI need to modify **models.py**. Please review the proposed changes:\n\n```python\n{file_content}\n```\n\nDo you approve these changes?",
                    actions=actions,
                    author="System"
                )
                await msg.send()
                break

@cl.on_message
async def on_message(message: cl.Message):
    graph = cl.user_session.get("graph")
    config = cl.user_session.get("config")
    
    state = graph.get_state(config)
    
    # If the graph hasn't started yet, send initial state
    if not state.values:
        initial_state = {
            "task": message.content,
            "workspace_dir": WORKSPACE_DIR,
            "messages": [],
            "pending_tool_calls": [],
            "tool_outputs": []
        }
        await process_graph_stream(graph, initial_state, config)
    else:
        # If the graph has already run, we append the human message
        graph.update_state(config, {"messages": [HumanMessage(content=message.content)]})
        await process_graph_stream(graph, None, config)

@cl.action_callback("approve_changes")
async def on_action(action: cl.Action):
    # Remove the buttons from the chat
    await action.remove()
    
    graph = cl.user_session.get("graph")
    config = cl.user_session.get("config")
    
    if action.value == "approve":
        await cl.Message(content="✅ Changes approved! Resuming execution...", author="User").send()
        # Resume graph
        await process_graph_stream(graph, None, config)
    else:
        await cl.Message(content="❌ Changes rejected! Injecting failure...", author="User").send()
        
        state = graph.get_state(config)
        last_ai_msg = state.values["messages"][-1]
        
        tool_messages = []
        for t in last_ai_msg.tool_calls:
            if t["name"] == "write_file" and "models.py" in t["args"].get("filepath", ""):
                msg_content = "Error: User denied permission to modify models.py."
            else:
                msg_content = "Error: Tool execution cancelled because models.py modification was denied. Please retry without modifying models.py or ask for clarification."
            
            tool_messages.append(ToolMessage(
                tool_call_id=t["id"],
                name=t["name"],
                content=msg_content
            ))
        
        # Inject the tool errors directly into the execute_tools node
        graph.update_state(config, {"messages": tool_messages}, as_node="execute_tools")
        await process_graph_stream(graph, None, config)
