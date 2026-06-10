import json
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import GraphState
from tools import AGENT_TOOLS

# Initialize LLM (DeepSeek v4 Flash via OpenAI API format)
# Note: In production, replace base_url and api_key with actual DeepSeek credentials
llm = ChatOpenAI(
    model="deepseek-chat", # Placeholder for deepseek v4 flash
    base_url="https://api.deepseek.com/v1",
    api_key="your-api-key-here",
    temperature=0
).bind_tools(AGENT_TOOLS)

def analyze_task(state: GraphState):
    """Initializes the prompt and context."""
    system_prompt = f"""You are an expert Django developer agent.
Your current workspace is: {state['workspace_dir']}
Your workflow is strict:
1. Check models.py first.
2. If models.py needs modification, propose the change. (Wait for user permission).
3. Write views.py logic based on models.
4. Add urls.py to link views.
5. Check TS API examples in the boilerplate and generate frontend TS API.
"""
    return {"messages": [SystemMessage(content=system_prompt), HumanMessage(content=state["task"])]}

def agent_reasoning(state: GraphState):
    """Core LLM reasoning and tool calling."""
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

def should_continue(state: GraphState):
    """Determines the next node after reasoning."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return END

    # Check if any tool call is writing to models.py
    for tool_call in last_message.tool_calls:
        if tool_call["name"] == "write_file":
            args = tool_call["args"]
            if "models.py" in args.get("filepath", ""):
                return "ask_permission"
                
    return "execute_tools"

def execute_tools(state: GraphState):
    """
    Executes tools proposed by the LLM. 
    This node handles read-only tools and writes that don't target models.py.
    If the graph was paused at `ask_permission` and the user approved, 
    the execution flows into here and all pending tool calls are executed.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_messages = []
    tool_by_name = {t.name: t for t in AGENT_TOOLS}
    
    for tool_call in last_message.tool_calls:
        tool = tool_by_name.get(tool_call["name"])
        if tool:
            try:
                result = tool.invoke(tool_call["args"])
                tool_messages.append(ToolMessage(tool_call_id=tool_call["id"], name=tool_call["name"], content=str(result)))
            except Exception as e:
                tool_messages.append(ToolMessage(tool_call_id=tool_call["id"], name=tool_call["name"], content=f"Error executing tool: {e}"))
        
    return {"messages": tool_messages}

def ask_permission(state: GraphState):
    """
    This node serves as the interrupt point. 
    Execution pauses *before* entering this node if configured with `interrupt_before`.
    When resumed, we just pass through to execute_tools.
    """
    pass

def build_graph():
    workflow = StateGraph(GraphState)
    
    workflow.add_node("analyze_task", analyze_task)
    workflow.add_node("agent_reasoning", agent_reasoning)
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_node("ask_permission", ask_permission)
    
    workflow.set_entry_point("analyze_task")
    
    workflow.add_edge("analyze_task", "agent_reasoning")
    
    workflow.add_conditional_edges(
        "agent_reasoning",
        should_continue,
        {
            "ask_permission": "ask_permission",
            "execute_tools": "execute_tools",
            END: END
        }
    )
    
    workflow.add_edge("execute_tools", "agent_reasoning")
    workflow.add_edge("ask_permission", "execute_tools") # Once approved, execute it
    
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory, interrupt_before=["ask_permission"])
    return graph
