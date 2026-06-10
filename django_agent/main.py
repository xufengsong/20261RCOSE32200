import uuid
from langchain_core.messages import ToolMessage
from graph import build_graph

def main():
    graph = build_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    task = "Create a Post model with title and content, then create the views and ts api."
    workspace_dir = "my_django_project"
    
    initial_state = {
        "task": task,
        "workspace_dir": workspace_dir,
        "messages": [],
        "pending_tool_calls": [],
        "tool_outputs": []
    }
    
    print("Starting agent...")
    for event in graph.stream(initial_state, config, stream_mode="values"):
        last_msg = event.get("messages", [])[-1] if event.get("messages") else None
        if last_msg:
             # Basic print to show progress
            print(f"[{last_msg.type.upper()}]: {str(last_msg.content)[:100]}")
    
    # Check if we are interrupted
    state = graph.get_state(config)
    if state.next and state.next[0] == "ask_permission":
        print("\n--- HUMAN IN THE LOOP REQUIRED ---")
        last_ai_msg = state.values["messages"][-1]
        
        # Find the tool call for models.py
        for tc in last_ai_msg.tool_calls:
            if tc["name"] == "write_file" and "models.py" in tc["args"].get("filepath", ""):
                print(f"Agent wants to modify models.py:\nFile: {tc['args']['filepath']}\nContent:\n{tc['args']['content'][:200]}...")
                
                decision = input("Approve this change? (y/n): ")
                
                if decision.lower() == 'y':
                    print("Approved. Resuming graph...")
                    # Resume graph to process the ask_permission and move to execute_tools
                    for event in graph.stream(None, config, stream_mode="values"):
                        pass
                else:
                    print("Rejected. Injecting failure...")
                    # We must provide a ToolMessage response for EVERY tool call in the AIMessage 
                    # to prevent the LLM provider (like OpenAI/DeepSeek) from throwing an error.
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
                    
                    # Update state with the rejection messages, simulating that 'execute_tools' handled them.
                    graph.update_state(config, {"messages": tool_messages}, as_node="execute_tools")
                    
                    # Resume graph (it will move from execute_tools -> agent_reasoning)
                    for event in graph.stream(None, config, stream_mode="values"):
                        pass

if __name__ == "__main__":
    main()
