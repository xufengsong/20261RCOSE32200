import operator
from typing import Annotated, TypedDict, List
from langchain_core.messages import AnyMessage

class GraphState(TypedDict):
    """
    Represents the state of our agent.
    """
    task: str
    workspace_dir: str
    messages: Annotated[List[AnyMessage], operator.add]
    # For handling human-in-the-loop tool execution
    pending_tool_calls: list
    tool_outputs: list
