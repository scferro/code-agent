## 22. examples/simple_task.py
import os
from pathlib import Path
import tempfile
import shutil
import sys

# Add parent directory to path to import codeagent
sys.path.insert(0, str(Path(__file__).parent.parent))

from codeagent.agent.code_agent import CodeAgent

def main():
    """Run a simple coding task example"""
    # Create a temporary directory for the example project
    example_dir = tempfile.mkdtemp()
    print(f"Created example project directory: {example_dir}")
    
    try:
        # Create a simple project structure
        create_example_project(example_dir)
        
        # Initialize the agent
        agent = CodeAgent(example_dir, verbose=True)
        
        # Define a simple task
        task = "Create a function to calculate the factorial of a number recursively."
        
        print(f"\nExecuting task: {task}\n")
        
        # Process the task
        solution = agent.process_task(task)
        
        # Print the solution
        print("\nGenerated Solution:")
        print("-" * 50)
        print(solution)
        print("-" * 50)
        
    finally:
        # Clean up
        shutil.rmtree(example_dir)
        print(f"Cleaned up example project directory: {example_dir}")

def create_example_project(project_dir):
    """Create a simple project structure for the example"""
    # Create directories
    os.makedirs(os.path.join(project_dir, "src"))
    os.makedirs(os.path.join(project_dir, "tests"))
    
    # Create .agent.md file
    with open(os.path.join(project_dir, ".agent.md"), "w") as f:
        f.write("""# Example Project

## Project Description
A simple example project for demonstrating CodeAgent.

## Architecture
Simple Python project with src and tests directories.

## Code Style
PEP 8

## Common Commands
- Run: `python -m src.main`
- Test: `pytest`

## File Descriptions
- `src/`: Source code directory
- `tests/`: Test directory
- `README.md`: Project documentation
""")
    
    # Create main.py
    with open(os.path.join(project_dir, "src", "main.py"), "w") as f:
        f.write("""def main():
    print("Hello, world!")

if __name__ == "__main__":
    main()
""")
    
    # Create utils.py (empty)
    with open(os.path.join(project_dir, "src", "utils.py"), "w") as f:
        f.write("""# Utility functions

""")
    
    # Create README.md
    with open(os.path.join(project_dir, "README.md"), "w") as f:
        f.write("""# Example Project

A simple example project for demonstrating CodeAgent.
""")

if __name__ == "__main__":
    main()