"""Workflow definitions for the code agent"""
from typing import Dict, List, Any, Optional, Callable
import json
from langchain.schema import HumanMessage, AIMessage

class AgentWorkflow:
    """Base class for agent workflows"""
    
    def __init__(self, agent_executor, memory, project_context):
        self.agent_executor = agent_executor
        self.memory = memory
        self.project_context = project_context
    
    def add_system_message(self, content: str):
        """Add a system message to the memory"""
        self.memory.chat_memory.add_ai_message(content)
    
    def add_user_message(self, content: str):
        """Add a user message to the memory"""
        self.memory.chat_memory.add_human_message(content)
    
    def run_step(self, input_message: str) -> Dict[str, Any]:
        """Run a single step of the workflow"""
        return self.agent_executor.invoke({"input": input_message})

class TaskWorkflow(AgentWorkflow):
    """Workflow for processing a coding task"""
    
    def execute(self, task_description: str) -> str:
        """Execute the full task workflow"""
        # Add task message
        self.add_user_message(f"Task: {task_description}")
        
        # Run task execution
        result = self.run_step(task_description)
        
        return result.get("output", "No response generated")