"""Tests for the CodeAgent class"""
import unittest
from pathlib import Path
import tempfile
import os
import shutil

from codeagent.agent.code_agent import CodeAgent

class TestCodeAgent(unittest.TestCase):
    """Tests for the CodeAgent class"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary directory
        self.test_dir = tempfile.mkdtemp()
        
        # Create a simple project structure
        self._create_test_project()
        
        # Initialize agent
        self.agent = CodeAgent(self.test_dir, verbose=True)
    
    def tearDown(self):
        """Clean up test environment"""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
    
    def _create_test_project(self):
        """Create a simple project structure for testing"""
        # Create directories
        os.makedirs(os.path.join(self.test_dir, "src"))
        os.makedirs(os.path.join(self.test_dir, "tests"))
        
        # Create .agent.md file
        with open(os.path.join(self.test_dir, ".agent.md"), "w") as f:
            f.write("""# Test Project

## Project Description
A simple test project for testing the CodeAgent.

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
        with open(os.path.join(self.test_dir, "src", "main.py"), "w") as f:
            f.write("""def main():
    print("Hello, world!")

if __name__ == "__main__":
    main()
""")
        
        # Create test_main.py
        with open(os.path.join(self.test_dir, "tests", "test_main.py"), "w") as f:
            f.write("""import unittest
from src.main import main

class TestMain(unittest.TestCase):
    def test_main(self):
        # Test that main runs without errors
        main()

if __name__ == "__main__":
    unittest.main()
""")
        
        # Create README.md
        with open(os.path.join(self.test_dir, "README.md"), "w") as f:
            f.write("""# Test Project

A simple test project for testing the CodeAgent.
""")
    
    def test_initialization(self):
        """Test agent initialization"""
        # Check that agent is created
        self.assertIsNotNone(self.agent)
        
        # Check that project context is created
        self.assertIsNotNone(self.agent.project_context)
        
        # Check that static context is loaded
        static_context = self.agent.project_context.get_static_context_summary()
        self.assertIn("Test Project", static_context)
    
    # Note: The following test is commented out because it would actually call Ollama
    # Uncomment and run manually when needed
    """
    def test_chat(self):
        """Test chat interaction"""
        # Simple chat interaction
        response = self.agent.chat("What files are in this project?")
        
        # Check response
        self.assertIsInstance(response, str)
        self.assertIn("main.py", response)
    """

if __name__ == "__main__":
    unittest.main()