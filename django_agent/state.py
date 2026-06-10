import operator
from typing import Annotated, TypedDict, List
from langchain_core.messages import AnyMessage

class GraphState(TypedDict):
    """
    Represents the internal state of the LangGraph agent during execution.
    
    Attributes:
        task: The original task requested by the user.
        workspace_dir: The directory path where the Django boilerplate resides.
        messages: A list of messages (System, Human, AI, Tool) tracking the conversation.
                  The `operator.add` reducer ensures messages are appended rather than overwritten.
        pending_tool_calls: (Optional) Used to track tool calls waiting for manual human-in-the-loop review.
        tool_outputs: (Optional) Used to track the results of manually approved/rejected tool calls.
    """
    task: str
    workspace_dir: str
    messages: Annotated[List[AnyMessage], operator.add]
    pending_tool_calls: list
    tool_outputs: list
