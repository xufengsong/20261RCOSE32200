import os
from typing import List
from langchain_core.tools import tool

@tool
def read_file(filepath: str) -> str:
    """Reads the contents of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def write_file(filepath: str, content: str) -> str:
    """Writes content to a file. Use this for modifying models.py, views.py, etc."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {filepath}"
    except Exception as e:
        return f"Error writing file: {e}"

@tool
def list_directory(path: str) -> List[str]:
    """Lists files and directories in the given path."""
    try:
        return os.listdir(path)
    except Exception as e:
        return [f"Error listing directory: {e}"]

# List of all tools available to the agent
AGENT_TOOLS = [read_file, write_file, list_directory]
