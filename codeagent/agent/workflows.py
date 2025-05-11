"""Workflow definitions for the code agent, including phase protocols"""
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


# Phase Protocol Definitions
# These schemas define the expected formats for phase inputs and outputs

PLANNING_PHASE_SCHEMA = {
    "type": "object",
    "properties": {
        "plan": {
            "type": "array",
            "description": "A list of steps to complete the task",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer", "description": "The step number"},
                    "description": {"type": "string", "description": "Description of what to do in this step"},
                    "expected_result": {"type": "string", "description": "What will be achieved after this step"}
                },
                "required": ["step_number", "description"]
            }
        },
        "success_criteria": {
            "type": "array",
            "description": "Criteria to verify the task is completed successfully",
            "items": {"type": "string"}
        }
    },
    "required": ["plan"]
}

EXECUTION_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "description": "Status of execution (completed, failed, etc.)"},
        "details": {"type": "string", "description": "Details about the execution"}
    },
    "required": ["status"]
}

VERIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "successful": {"type": "boolean", "description": "Whether verification was successful"},
        "issues": {
            "type": "array",
            "description": "List of issues found during verification",
            "items": {"type": "string"}
        },
        "summary": {"type": "string", "description": "Summary of the verification"}
    },
    "required": ["successful", "summary"]
}

def format_planning_prompt(task: str) -> str:
    """Format the planning phase prompt.

    Args:
        task: The task description

    Returns:
        A formatted planning prompt
    """
    schema_json = json.dumps(PLANNING_PHASE_SCHEMA, indent=2)

    return f"""PLANNING PHASE: You are in the planning phase for the current task.

TASK: {task}

AVAILABLE PHASE ACTIONS:
- complete_planning - Completes the planning phase and transitions to execution
  - parameters: {{ "plan": {{ "plan": [steps], "success_criteria": [criteria] }} }}

PLANNING INSTRUCTIONS:
1. For simple tasks (like creating a file), a minimal plan with 1-2 steps is sufficient
2. For complex tasks, break down into 3-7 actionable steps
3. Include step_number, description, and expected_result for each step
4. Define clear success criteria to verify task completion
5. Use the complete_planning action to submit your plan and move to execution phase

PLAN SCHEMA:
{schema_json}

Example plan for a simple task:
{{
  "plan": [
    {{
      "step_number": 1,
      "description": "Create the requested file with appropriate content",
      "expected_result": "File created with requested content"
    }}
  ],
  "success_criteria": ["File exists", "File contains the requested content"]
}}

Example plan for a complex task:
{{
  "plan": [
    {{
      "step_number": 1,
      "description": "Analyze existing code structure",
      "expected_result": "Understanding of where changes need to be made"
    }},
    {{
      "step_number": 2,
      "description": "Implement the required functionality",
      "expected_result": "Working implementation that meets requirements"
    }},
    {{
      "step_number": 3,
      "description": "Test the implementation",
      "expected_result": "Verified working solution"
    }}
  ],
  "success_criteria": ["Code correctly implements the requirements", "Implementation follows project patterns"]
}}

IMPORTANT: When your plan is ready, use the complete_planning action to submit it and proceed to execution.
"""

def format_execution_prompt(plan: Dict[str, Any], current_step: int = None) -> str:
    """Format the execution phase prompt.

    Args:
        plan: The plan from the planning phase
        current_step: The current step number (optional)

    Returns:
        A formatted execution prompt
    """
    steps_json = json.dumps(plan.get("plan", []), indent=2)

    return f"""EXECUTION PHASE: You are implementing the solution according to your plan.

AVAILABLE PHASE ACTIONS:
- complete_execution - Completes the execution phase and transitions to verification
  - parameters: {{ "status": "completed or failed", "details": "execution details" }}

YOUR PLAN:
{steps_json}

EXECUTION INSTRUCTIONS:
1. Implement each step in your plan methodically
2. Use standard tools (read_file, write_file, etc.) to complete the task
3. When finished, use the complete_execution action to move to verification

Example execution completion (success):
{{
  "action": "complete_execution",
  "parameters": {{
    "status": "completed",
    "details": "Successfully implemented all steps according to the plan"
  }}
}}

Example execution completion (with issues):
{{
  "action": "complete_execution",
  "parameters": {{
    "status": "completed with issues",
    "details": "Implemented core functionality but encountered an issue with X"
  }}
}}

IMPORTANT: After implementing the solution, use complete_execution to proceed to verification.
"""

def format_verification_prompt(success_criteria: List[str]) -> str:
    """Format the verification phase prompt.

    Args:
        success_criteria: The list of success criteria from the planning phase

    Returns:
        A formatted verification prompt
    """
    criteria_text = "\n".join([f"- {criterion}" for criterion in success_criteria])

    return f"""VERIFICATION PHASE: You are verifying that the implementation meets all success criteria.

AVAILABLE PHASE ACTIONS:
- complete_verification - Completes the verification phase and finalizes the task
  - parameters: {{ "successful": true/false, "issues": [], "summary": "verification summary" }}

SUCCESS CRITERIA TO VERIFY:
{criteria_text}

VERIFICATION INSTRUCTIONS:
1. Review each success criterion carefully
2. Check if the implementation satisfies each criterion
3. Document any issues found
4. Make a final determination (successful or not)
5. Use the complete_verification action when done

Example verification (success):
{{
  "action": "complete_verification",
  "parameters": {{
    "successful": true,
    "issues": [],
    "summary": "All success criteria have been met. The implementation is correct and follows project standards."
  }}
}}

Example verification (failure):
{{
  "action": "complete_verification",
  "parameters": {{
    "successful": false,
    "issues": ["Missing error handling in function X", "Test case Y fails"],
    "summary": "The implementation has issues that need to be addressed."
  }}
}}

IMPORTANT: If verification fails, you'll return to the planning phase to address the issues.
"""

def validate_phase_output(phase: str, output: Dict[str, Any]) -> bool:
    """Validate that the phase output matches the expected schema.

    Args:
        phase: The phase name (planning, execution, verification)
        output: The output to validate

    Returns:
        True if valid, False otherwise
    """
    print(f"DEBUG - Validating {phase} output: {output}")

    # For planning phase, check if we have a plan with steps
    if phase == "planning":
        # Check for plan array with at least one step containing step_number and description
        if "plan" not in output:
            print(f"DEBUG - Validation failed: missing 'plan' key")
            return False

        plan_array = output.get("plan", [])
        if not isinstance(plan_array, list) or not plan_array:
            print(f"DEBUG - Validation failed: 'plan' is not a non-empty list")
            return False

        first_step = plan_array[0]
        if not isinstance(first_step, dict):
            print(f"DEBUG - Validation failed: first step is not a dict")
            return False

        if "step_number" not in first_step or "description" not in first_step:
            print(f"DEBUG - Validation failed: step missing required fields")
            return False

        print(f"DEBUG - Planning validation passed")
        return True

    # For execution phase, just check for status
    elif phase == "execution":
        has_status = "status" in output
        print(f"DEBUG - Execution validation {'passed' if has_status else 'failed'}")
        return has_status

    # For verification phase, check for successful flag and summary
    elif phase == "verification":
        has_required = "successful" in output and "summary" in output
        print(f"DEBUG - Verification validation {'passed' if has_required else 'failed'}")
        return has_required

    # Unknown phase
    print(f"DEBUG - Unknown phase: {phase}")
    return False