"""Tools for agent switching and coordination."""
from typing import List, Dict, Any, Optional
from enum import Enum
from langchain.tools import tool

class AgentType(Enum):
    """Enum for agent types."""
    MAIN = "main"
    SUB = "sub"

@tool
def invoke_agent(agent_type: str, prompt: str, conversation_state=None) -> str:
    """Invoke a sub-agent with a specific prompt.
    
    This tool switches from the main agent to a sub-agent, transferring control
    and providing a clean conversation context. The sub-agent shares file context
    but gets a focused environment for completing specific tasks.
    
    Args:
        agent_type: Must be "sub_agent" (the only supported sub-agent type)
        prompt: The task prompt for the sub-agent
        conversation_state: The current conversation state (injected automatically)
        
    Returns:
        A confirmation message that the agent was invoked
    """
    # Only accept "sub_agent" type
    if agent_type != "sub_agent":
        return f"Error: Invalid agent type '{agent_type}'. Only 'sub_agent' is supported."
    
    # Ensure conversation_state is provided (should be injected by the framework)
    if conversation_state is None:
        return "Error: Conversation state is required for agent switching."
    
    # Store the current main agent state before switching
    conversation_state.store_agent_state()
    
    # Switch to the sub agent
    conversation_state.switch_agent(AgentType.SUB)
    
    # Save the prompt for the subagent
    conversation_state.store_task_data("subagent_prompt", prompt)
    
    return f"Switched to sub-agent with prompt: {prompt}"

@tool
def respond_to_master(response: str, conversation_state=None) -> str:
    """Return control to the main agent with a response.
    
    This tool is used by sub-agents to return control to the main agent,
    providing a detailed response about their findings or actions.
    
    Args:
        response: The detailed response to send back to the main agent
        conversation_state: The current conversation state (injected automatically)
        
    Returns:
        A confirmation message that control was returned to the main agent
    """
    # Ensure conversation_state is provided (should be injected by the framework)
    if conversation_state is None:
        return "Error: Conversation state is required for agent switching."
    
    # Store this sub-agent's result
    current_agent = conversation_state.current_agent
    conversation_state.store_task_data(f"{current_agent.value}_result", response)
    
    # Store the current sub-agent state before switching back
    conversation_state.store_agent_state()
    
    # Switch back to the main agent
    conversation_state.switch_agent(AgentType.MAIN)
    
    # Return a confirmation message
    return f"Returned to main agent with response from {current_agent.value} agent."

def get_agent_tools():
    """Get all agent-related tools."""
    return [
        invoke_agent,
        respond_to_master
    ]