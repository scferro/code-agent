"""Workflow definitions for the code agent"""
from typing import Dict, List, Any, Optional
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
        # Phase 1: Exploration
        exploration_result = self.exploration_phase(task_description)
        
        # Phase 2: Planning
        plan = self.planning_phase(task_description, exploration_result)
        
        # Phase 3: Execution
        solution = self.execution_phase(task_description, plan)
        
        # Phase 4: Verification
        verified_solution = self.verification_phase(solution)
        
        return verified_solution
    
    def exploration_phase(self, task: str) -> str:
        """Execute the exploration phase"""
        # Add phase prompt
        self.add_user_message(f"EXPLORATION PHASE: Explore the codebase to solve: {task}")
        
        # Run exploration
        result = self.run_step(f"Let's explore the codebase to understand how to implement: {task}")
        
        # Get summary
        summary_result = self.run_step("Summarize what you've learned about this codebase.")
        
        return summary_result["output"]
    
    def planning_phase(self, task: str, exploration_result: str) -> str:
        """Execute the planning phase"""
        # Add phase prompt
        self.add_user_message(f"PLANNING PHASE: Create a step-by-step plan to implement: {task}")
        
        # Run planning
        result = self.run_step(f"Based on our exploration, let's create a detailed plan to implement: {task}")
        
        return result["output"]
    
    def execution_phase(self, task: str, plan: str) -> str:
        """Execute the execution phase"""
        # Add phase prompt
        self.add_user_message(f"EXECUTION PHASE: Implement the solution according to our plan.")
        
        # Run execution
        result = self.run_step("Let's implement the solution according to our plan.")
        
        return result["output"]
    
    def verification_phase(self, solution: str) -> str:
        """Execute the verification phase"""
        # Add phase prompt
        self.add_user_message("VERIFICATION PHASE: Review and improve the solution.")
        
        # Run verification
        result = self.run_step("Let's review our solution for any issues or improvements.")
        
        # Get final solution
        final_result = self.run_step("Please provide the complete final solution with all improvements.")
        
        return final_result["output"]