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
                    "expected_result": {"type": "string", "description": "What will be achieved after this step"},
                    "verification": {"type": "string", "description": "How to verify this step was completed successfully"}
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
        "details": {"type": "string", "description": "Details about the execution"},
        "verification_results": {
            "type": "array",
            "description": "Results of verifying each step",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer", "description": "The step number that was verified"},
                    "successful": {"type": "boolean", "description": "Whether the step was verified successfully"},
                    "notes": {"type": "string", "description": "Notes about the verification result"}
                }
            }
        }
    },
    "required": ["status"]
}

# VERIFICATION_SCHEMA is no longer used - verification is integrated into execution

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
3. Include step_number, description, expected_result, and verification for each step
4. The verification field should describe how to check if the step was done correctly
5. Define clear success criteria to verify overall task completion
6. Use the complete_planning action to submit your plan and move to execution phase

PLAN SCHEMA:
{schema_json}

Example plan for a simple task:
{{
  "plan": [
    {{
      "step_number": 1,
      "description": "Create the requested file with appropriate content",
      "expected_result": "File created with requested content",
      "verification": "Check that the file exists and contains the expected content"
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
      "expected_result": "Understanding of where changes need to be made",
      "verification": "Confirm we've identified the relevant files and functions to modify"
    }},
    {{
      "step_number": 2,
      "description": "Implement the required functionality",
      "expected_result": "Working implementation that meets requirements",
      "verification": "Run syntax checks on the code and verify implementation matches requirements"
    }},
    {{
      "step_number": 3,
      "description": "Test the implementation",
      "expected_result": "Verified working solution",
      "verification": "Run the code and confirm it produces the expected output"
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
    criteria_json = json.dumps(plan.get("success_criteria", []), indent=2)

    return f"""EXECUTION PHASE: You are implementing the solution according to your plan.

AVAILABLE PHASE ACTIONS:
- complete_task - Completes the task when all steps are executed and verified
  - parameters: {{ "status": "completed or failed", "details": "execution details", "verification_results": [results] }}

YOUR PLAN:
{steps_json}

SUCCESS CRITERIA:
{criteria_json}

EXECUTION INSTRUCTIONS:
1. Implement each step in your plan methodically
2. Use standard tools (read_file, write_file, etc.) to complete the task
3. After implementing each step, verify it worked as expected
4. When all steps are complete and verified, use the complete_task action

Example step verification process:
1. Implement step 1: "Create config file"
2. Verify the file was created correctly by reading it back
3. Record verification results: successful=true, notes="Config file created with correct settings"
4. Proceed to the next step

Example task completion (success):
{{
  "action": "complete_task",
  "parameters": {{
    "status": "completed",
    "details": "Successfully implemented all steps according to the plan",
    "verification_results": [
      {{ "step_number": 1, "successful": true, "notes": "Step 1 verification passed" }},
      {{ "step_number": 2, "successful": true, "notes": "Step 2 verification passed" }}
    ]
  }}
}}

Example task completion (with issues):
{{
  "action": "complete_task",
  "parameters": {{
    "status": "completed with issues",
    "details": "Implemented core functionality but encountered an issue with step 2",
    "verification_results": [
      {{ "step_number": 1, "successful": true, "notes": "Step 1 verification passed" }},
      {{ "step_number": 2, "successful": false, "notes": "Step 2 failed: could not connect to database" }}
    ]
  }}
}}

IMPORTANT: After implementing AND verifying all steps, use complete_task to finish the task.
"""

def format_planning_examples() -> str:
    """Return a string with example plans for various common coding tasks.
    
    These examples are meant to guide the agent in creating appropriate plans
    for different types of coding tasks.
    
    Returns:
        A formatted string containing example plans
    """
    return """
# Example Plans for Common Coding Tasks

## 1. List Files in a Project Directory
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Use list_files tool to get the top-level directories and files",
      "expected_result": "List of main directories and files in the root directory",
      "verification": "Successfully received a non-empty list of files and directories"
    },
    {
      "step_number": 2,
      "description": "Identify key project files (package.json, README.md, etc.) from the results",
      "expected_result": "List of important configuration and documentation files",
      "verification": "Identified at least 2-3 key files that provide project information"
    },
    {
      "step_number": 3,
      "description": "Use list_files with recursive=true to explore src/ or lib/ directory if present",
      "expected_result": "Deeper view of the project's source code structure",
      "verification": "Successfully received a list of files in the source directory"
    },
    {
      "step_number": 4,
      "description": "Compile the findings into a clear directory structure summary",
      "expected_result": "Organized summary of the project's file structure",
      "verification": "Summary includes both top-level and important subdirectories"
    }
  ],
  "success_criteria": [
    "Retrieved complete list of top-level directories and files",
    "Identified key project files (README, configuration files, etc.)",
    "Explored at least one level of source code directories",
    "Presented an organized view of the project structure"
  ]
}
```

## 2. Read and Analyze a Specific File
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Use read_file tool to read the specified file (e.g., package.json)",
      "expected_result": "Full content of the target file",
      "verification": "Successfully retrieved the file content without errors"
    },
    {
      "step_number": 2,
      "description": "Parse the file content based on its format (JSON, JavaScript, etc.)",
      "expected_result": "Structured understanding of the file's data or code",
      "verification": "Successfully parsed the content without syntax errors"
    },
    {
      "step_number": 3,
      "description": "Extract key information from the file (dependencies, main exports, etc.)",
      "expected_result": "List of important elements from the file",
      "verification": "Identified specific key information relevant to the file type"
    },
    {
      "step_number": 4,
      "description": "Format the findings into a clear, concise summary",
      "expected_result": "User-friendly summary of the file's purpose and content",
      "verification": "Summary accurately represents the file's key information"
    }
  ],
  "success_criteria": [
    "Successfully read the complete file content",
    "Correctly parsed the file based on its format",
    "Extracted relevant key information from the file",
    "Provided a clear explanation of the file's purpose and content"
  ]
}
```

## 3. Search for a Specific Function in the Codebase
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Use search_code tool with the exact function name (e.g., 'function calculateTotal')",
      "expected_result": "List of files containing the function name",
      "verification": "Search returned at least one result containing the function"
    },
    {
      "step_number": 2,
      "description": "Read the first file that contains the function using read_file",
      "expected_result": "Content of the file with the target function",
      "verification": "Successfully retrieved the file content containing the function"
    },
    {
      "step_number": 3,
      "description": "Locate the specific function definition in the file content",
      "expected_result": "Exact function implementation code",
      "verification": "Found the complete function definition including parameters and body"
    },
    {
      "step_number": 4,
      "description": "Analyze the function's parameters, return value, and implementation details",
      "expected_result": "Understanding of what the function does and how it works",
      "verification": "Correctly identified parameters, return value, and main logic"
    }
  ],
  "success_criteria": [
    "Successfully found the file containing the function",
    "Located the exact function definition in the file",
    "Correctly identified function parameters and return value",
    "Accurately described what the function does"
  ]
}
```

## 4. Create a New Python File
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Determine the appropriate directory for the new Python file",
      "expected_result": "Target path for the new Python file",
      "verification": "Directory exists and follows project structure conventions"
    },
    {
      "step_number": 2,
      "description": "Use list_files to check if a file with the same name already exists",
      "expected_result": "Confirmation that we're not overwriting an existing file",
      "verification": "Confirmed the file doesn't already exist at the target path"
    },
    {
      "step_number": 3,
      "description": "Create Python file skeleton with appropriate imports and docstring",
      "expected_result": "Well-structured Python file template",
      "verification": "File template includes proper module docstring, imports, and structure"
    },
    {
      "step_number": 4,
      "description": "Add the requested class(es) and function(s) with appropriate docstrings",
      "expected_result": "Python file with all requested functionality",
      "verification": "Code includes all required classes/functions with proper documentation"
    },
    {
      "step_number": 5,
      "description": "Add any necessary helper functions or constants",
      "expected_result": "Complete implementation with all supporting code",
      "verification": "All required helper functions and constants are implemented"
    },
    {
      "step_number": 6,
      "description": "Add main execution section with if __name__ == '__main__'",
      "expected_result": "Executable Python file with example usage",
      "verification": "File includes main section that demonstrates usage"
    },
    {
      "step_number": 7,
      "description": "Use write_file tool to create the file with the prepared content",
      "expected_result": "New Python file created at the target location",
      "verification": "File successfully created with valid Python content"
    }
  ],
  "success_criteria": [
    "Python file created at the appropriate location",
    "File includes proper documentation and follows PEP 8 style guidelines",
    "Implementation correctly implements all requested functionality",
    "Code includes appropriate error handling and input validation",
    "File includes example usage in main section"
  ]
}
```

## 5. Edit an Existing Python File
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Use read_file to read the Python file that needs to be edited",
      "expected_result": "Current content of the Python file",
      "verification": "Successfully retrieved the complete file content"
    },
    {
      "step_number": 2,
      "description": "Analyze the file structure to locate where changes need to be made",
      "expected_result": "Identification of exact locations for edits",
      "verification": "Correctly identified all sections that need modification"
    },
    {
      "step_number": 3,
      "description": "Make the requested modifications to imports if necessary",
      "expected_result": "Updated import section with any new required imports",
      "verification": "All necessary imports are added in the appropriate format"
    },
    {
      "step_number": 4,
      "description": "Implement changes to the specified function or class",
      "expected_result": "Updated function/class with requested changes",
      "verification": "Function/class modification preserves existing functionality while adding new features"
    },
    {
      "step_number": 5,
      "description": "Update docstrings and comments to reflect the changes",
      "expected_result": "Documentation that accurately describes the modified code",
      "verification": "Docstrings and comments correctly reflect the updated functionality"
    },
    {
      "step_number": 6,
      "description": "Ensure code style consistency throughout the modified sections",
      "expected_result": "Code that maintains the project's style conventions",
      "verification": "Modified code follows the same style as the existing codebase"
    },
    {
      "step_number": 7,
      "description": "Use write_file to update the file with the modified content",
      "expected_result": "Python file updated with the new changes",
      "verification": "File successfully updated with all requested modifications"
    }
  ],
  "success_criteria": [
    "All requested changes successfully implemented",
    "Existing functionality preserved unless explicitly meant to be changed",
    "Documentation updated to reflect the changes",
    "Code style consistent with the rest of the file",
    "No syntax errors or logical issues introduced"
  ]
}
```

## 6. Update an Existing Configuration File
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Use read_file to read the current configuration file (e.g., package.json)",
      "expected_result": "Current content of the configuration file",
      "verification": "Successfully retrieved the complete file content"
    },
    {
      "step_number": 2,
      "description": "Parse the configuration content into a structured format",
      "expected_result": "Parsed configuration data that can be modified",
      "verification": "Successfully parsed the file content without errors"
    },
    {
      "step_number": 3,
      "description": "Make the specific requested changes to the configuration",
      "expected_result": "Updated configuration with the requested changes",
      "verification": "Changes correctly applied to the parsed configuration"
    },
    {
      "step_number": 4,
      "description": "Format the updated configuration back to the appropriate string format",
      "expected_result": "Properly formatted configuration string",
      "verification": "Formatting matches the original file style and indentation"
    },
    {
      "step_number": 5,
      "description": "Use write_file to update the configuration file with the new content",
      "expected_result": "Configuration file updated with the new settings",
      "verification": "File successfully updated with the correct changes"
    }
  ],
  "success_criteria": [
    "Configuration file successfully updated",
    "All requested changes correctly implemented",
    "File formatting and structure maintained",
    "No syntax errors in the updated configuration"
  ]
}
```

## 7. Find and List All TODO Comments
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Use search_code tool with 'TODO' as the search term",
      "expected_result": "List of files containing TODO comments",
      "verification": "Search returned files containing TODO comments (or empty if none exist)"
    },
    {
      "step_number": 2,
      "description": "For each file in the results, use read_file to get its content",
      "expected_result": "Content of files containing TODOs",
      "verification": "Successfully retrieved content of each file with TODOs"
    },
    {
      "step_number": 3,
      "description": "Extract the exact TODO comments with their line numbers from each file",
      "expected_result": "List of TODO comments with locations",
      "verification": "Extracted all TODO comments with accurate line numbers"
    },
    {
      "step_number": 4,
      "description": "Format the findings into a structured report",
      "expected_result": "Organized report of all TODO comments in the project",
      "verification": "Report includes filename, line number, and full comment text for each TODO"
    }
  ],
  "success_criteria": [
    "Successfully found all files containing TODO comments",
    "Extracted all TODO comments with their exact locations",
    "Provided a comprehensive list organized by file",
    "Each TODO includes contextual information"
  ]
}
```

## 8. Add a New Function to an Existing Module
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Use read_file to read the module where the function should be added",
      "expected_result": "Current content of the target module",
      "verification": "Successfully retrieved the complete module content"
    },
    {
      "step_number": 2,
      "description": "Analyze the module structure to determine the appropriate location for the new function",
      "expected_result": "Specific position in the file to insert the new function",
      "verification": "Position follows logical organization of the module"
    },
    {
      "step_number": 3,
      "description": "Check if any new imports are needed for the function",
      "expected_result": "List of required imports to add (if any)",
      "verification": "Identified all necessary imports for the new function"
    },
    {
      "step_number": 4,
      "description": "Create the function with appropriate docstring and implementation",
      "expected_result": "Well-formatted function with complete implementation",
      "verification": "Function includes proper docstring, parameters, and implementation"
    },
    {
      "step_number": 5,
      "description": "Insert the function (and any new imports) into the module content",
      "expected_result": "Updated module content with the new function",
      "verification": "Function is properly inserted with correct indentation and formatting"
    },
    {
      "step_number": 6,
      "description": "Update any relevant unit tests or add example usage if appropriate",
      "expected_result": "Updated or new tests for the function",
      "verification": "Tests or examples demonstrating the function's usage"
    },
    {
      "step_number": 7,
      "description": "Use write_file to update the module with the new content",
      "expected_result": "Module updated with the new function",
      "verification": "File successfully updated with the new function"
    }
  ],
  "success_criteria": [
    "Function successfully added to the module",
    "Function has proper documentation and follows project style guidelines",
    "Function correctly implements the requested functionality",
    "Code organization is maintained in the updated module",
    "Any necessary tests or examples are included"
  ]
}
```

## 9. Execute a Simple git Status Command
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Check if we're in a git repository using a simple command",
      "expected_result": "Confirmation that we're in a git repository",
      "verification": "Command executed successfully and confirmed git repository status"
    },
    {
      "step_number": 2,
      "description": "Execute 'git status' command to get repository status",
      "expected_result": "Output showing current branch and file status",
      "verification": "Command executed successfully and returned status information"
    },
    {
      "step_number": 3,
      "description": "Parse the git status output to extract key information",
      "expected_result": "Structured information about branch and file status",
      "verification": "Successfully extracted current branch, changed files, and commit status"
    },
    {
      "step_number": 4,
      "description": "Format the findings into a clear status report",
      "expected_result": "User-friendly summary of the repository status",
      "verification": "Report accurately represents the current state of the repository"
    }
  ],
  "success_criteria": [
    "Successfully executed git status command",
    "Extracted current branch information",
    "Identified modified, added, and untracked files",
    "Provided a clear summary of the repository status"
  ]
}
```

## 10. Create a Simple HTML File
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Determine the appropriate directory for the new HTML file",
      "expected_result": "Target path for the new HTML file",
      "verification": "Directory exists and follows project conventions"
    },
    {
      "step_number": 2,
      "description": "Use list_files to check if a file with the same name already exists",
      "expected_result": "Confirmation that we're not overwriting an existing file",
      "verification": "Confirmed the file doesn't already exist at the target path"
    },
    {
      "step_number": 3,
      "description": "Create HTML skeleton with proper DOCTYPE, head, and body sections",
      "expected_result": "Well-structured HTML template",
      "verification": "HTML includes DOCTYPE declaration, title, and basic structure"
    },
    {
      "step_number": 4,
      "description": "Add the requested content to the HTML body",
      "expected_result": "HTML with all requested content elements",
      "verification": "Content includes all required sections and follows HTML standards"
    },
    {
      "step_number": 5,
      "description": "Add appropriate styling either inline or linked",
      "expected_result": "HTML with proper styling",
      "verification": "Styling enhances readability and follows basic design principles"
    },
    {
      "step_number": 6,
      "description": "Use write_file tool to create the file with the prepared HTML content",
      "expected_result": "New HTML file created at the target location",
      "verification": "File successfully created with valid HTML content"
    }
  ],
  "success_criteria": [
    "HTML file created at the appropriate location",
    "HTML is valid and well-structured",
    "Content meets all requirements",
    "File includes appropriate styling"
  ]
}
```

## 11. Add a New CSS Class to an Existing File
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Use read_file to read the CSS file that needs to be updated",
      "expected_result": "Current content of the CSS file",
      "verification": "Successfully retrieved the complete CSS file content"
    },
    {
      "step_number": 2,
      "description": "Determine the appropriate location to add the new CSS class",
      "expected_result": "Specific position in the file to insert the new class",
      "verification": "Position follows logical organization of the CSS file"
    },
    {
      "step_number": 3,
      "description": "Create the CSS class definition with the requested properties",
      "expected_result": "Well-formatted CSS class definition",
      "verification": "CSS syntax is valid and includes all requested properties"
    },
    {
      "step_number": 4,
      "description": "Insert the new CSS class into the file content at the determined position",
      "expected_result": "Updated CSS content with the new class",
      "verification": "New class is properly inserted with correct indentation and formatting"
    },
    {
      "step_number": 5,
      "description": "Use write_file to update the CSS file with the new content",
      "expected_result": "CSS file updated with the new class",
      "verification": "File successfully updated with the new CSS class"
    }
  ],
  "success_criteria": [
    "CSS file successfully updated with the new class",
    "New class has correct properties and values",
    "CSS syntax remains valid",
    "File formatting and structure maintained"
  ]
}
```

## 12. Check for Missing Import Statements
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Use read_file to read the JavaScript/TypeScript file to check",
      "expected_result": "Content of the file to be analyzed",
      "verification": "Successfully retrieved the complete file content"
    },
    {
      "step_number": 2,
      "description": "Extract all import statements from the file",
      "expected_result": "List of currently imported modules and components",
      "verification": "Successfully identified all existing import statements"
    },
    {
      "step_number": 3,
      "description": "Scan the file for references to modules that aren't imported",
      "expected_result": "List of modules/components used but not imported",
      "verification": "Identified all references to modules missing import statements"
    },
    {
      "step_number": 4,
      "description": "For each missing import, determine the likely import statement needed",
      "expected_result": "List of import statements that should be added",
      "verification": "Generated correct import statements for all missing imports"
    },
    {
      "step_number": 5,
      "description": "Create updated file content with the missing imports added",
      "expected_result": "File content with all necessary imports",
      "verification": "All missing imports are added in the appropriate format and location"
    },
    {
      "step_number": 6,
      "description": "Use write_file to update the file with the corrected imports",
      "expected_result": "File updated with all necessary imports",
      "verification": "File successfully updated with all missing imports added"
    }
  ],
  "success_criteria": [
    "Successfully identified all missing imports",
    "Added correct import statements for all missing modules",
    "Import statements added in the appropriate location",
    "File formatting and structure maintained"
  ]
}
```

## 13. Run and Analyze Unit Tests
```json
{
  "plan": [
    {
      "step_number": 1,
      "description": "Identify the test files that need to be run",
      "expected_result": "List of test files to execute",
      "verification": "Successfully identified all relevant test files"
    },
    {
      "step_number": 2,
      "description": "Execute the unit tests using the appropriate command",
      "expected_result": "Test execution results",
      "verification": "Tests executed successfully and produced output"
    },
    {
      "step_number": 3,
      "description": "Parse the test results to identify passing and failing tests",
      "expected_result": "Structured summary of test results",
      "verification": "Successfully extracted pass/fail status for each test"
    },
    {
      "step_number": 4,
      "description": "For failing tests, analyze the error messages to determine the cause",
      "expected_result": "List of failing tests with their error causes",
      "verification": "Accurately identified the reason for each test failure"
    },
    {
      "step_number": 5,
      "description": "Compile the findings into a detailed test report",
      "expected_result": "Comprehensive test report with pass/fail status and issues",
      "verification": "Report accurately represents the test results with useful analysis"
    }
  ],
  "success_criteria": [
    "Successfully executed all relevant tests",
    "Correctly identified passing and failing tests",
    "Provided clear analysis of test failures",
    "Generated a comprehensive test report"
  ]
}
```
"""

def validate_phase_output(phase: str, output: Dict[str, Any]) -> bool:
    """Validate that the phase output matches the expected schema.

    Args:
        phase: The phase name (planning, execution, done)
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

    # For execution phase, check for status and verification_results
    elif phase == "execution":
        has_status = "status" in output
        has_verification = "verification_results" in output
        print(f"DEBUG - Execution validation {'passed' if has_status else 'failed'}")
        return has_status  # We don't require verification_results to be present for backwards compatibility

    # Unknown phase (done phase doesn't need validation)
    print(f"DEBUG - Unknown phase: {phase}")
    return phase == "done"  # Phase "done" is always valid