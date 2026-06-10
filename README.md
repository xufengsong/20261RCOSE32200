# 20261RCOSE32200
Optional project for System Programming

## LangGraph Django Coding Agent

This repository contains a specialized coding agent built using LangChain and LangGraph. The agent is designed to automate Django backend development by following a strict, predefined workflow, powered by **DeepSeek v4 Flash**.

### Features

- **Automated Workflow**: The agent automatically analyzes a user request and applies it to a provided Django boilerplate.
- **Strict Execution Path**:
  1. Checks `models.py` first.
  2. Proposes changes to `models.py` (if any) and waits for user permission.
  3. Writes business logic in `views.py`.
  4. Updates `urls.py` to route traffic to the new views.
  5. Generates a frontend TypeScript API client by mimicking existing TS examples in the boilerplate.
- **Antigravity-style Human-in-the-Loop**: The agent uses LangGraph's `interrupt_before` capability to securely pause execution before modifying `models.py`. The user is prompted with the proposed changes and can approve or reject the tool execution.
- **Custom Tooling**: Uses custom LangChain file I/O tools for safe and restricted workspace access.

### Project Structure

The agent code is located in the `django_agent` directory:

- `requirements.txt`: Python dependencies (`langchain`, `langgraph`, `langchain-openai`, etc.).
- `state.py`: Defines the `GraphState` used to persist the workflow context.
- `tools.py`: Custom read/write file utilities for the agent.
- `graph.py`: The core LangGraph state machine defining the nodes and conditional edges.
- `main.py`: The CLI runner that handles the human-in-the-loop interruption and resumption.

### Usage

1. Navigate to the `django_agent` directory.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your DeepSeek API key in `graph.py`.
4. Run the agent:
   ```bash
   python main.py
   ```

*Note: Ensure you have a target Django boilerplate directory ready for the agent to manipulate.*
