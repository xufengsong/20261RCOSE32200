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
                    # We inject a tool message indicating rejection
                    tool_message = ToolMessage(
                        tool_call_id=tc["id"],
                        name=tc["name"],
                        content="Error: User denied permission to modify models.py"
                    )
                    # Update state with the rejection, then resume.
                    # We resume by updating the state as if the 'execute_tools' node returned the rejection.
                    graph.update_state(config, {"messages": [tool_message]}, as_node="execute_tools")
                    
                    for event in graph.stream(None, config, stream_mode="values"):
                        pass

if __name__ == "__main__":
    main()
