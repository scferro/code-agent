"""Tests for the project context module"""
import unittest
from pathlib import Path
import tempfile
import os
import shutil

from codeagent.context.project_context import ProjectContext
from codeagent.context.agent_md import AgentMdParser

class TestProjectContext(unittest.TestCase):
    """Tests for the ProjectContext class"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary directory
        self.test_dir = tempfile.mkdtemp()
        
        # Create a simple project structure
        self._create_test_project()
        
        # Initialize context
        self.context = ProjectContext(self.test_dir)
    
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
A simple test project for testing the context module.

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
    
    def test_load_static_context(self):
        """Test loading static context from .agent.md"""
        # Check that context is loaded
        self.assertIsNotNone(self.context.static_context)
        
        # Check specific fields
        self.assertEqual(
            self.context.static_context.get("project_description"),
            "A simple test project for testing the context module."
        )
        
        self.assertEqual(
            self.context.static_context.get("code_style"),
            "PEP 8"
        )
        
        # Check common commands
        self.assertIn("Run", self.context.static_context.get("common_commands", {}))
        self.assertEqual(
            self.context.static_context["common_commands"]["Run"],
            "python -m src.main"
        )
    
    def test_get_static_context_summary(self):
        """Test getting static context summary"""
        summary = self.context.get_static_context_summary()
        
        # Check summary content
        self.assertIn("Test Project", summary)
        self.assertIn("PEP 8", summary)
    
    def test_get_file_description(self):
        """Test getting file descriptions"""
        # Get description for src/
        desc = self.context.get_file_description("src/")
        self.assertEqual(desc, "Source code directory")
        
        # Get description for README.md
        desc = self.context.get_file_description("README.md")
        self.assertEqual(desc, "Project documentation")
    
    def test_get_file_structure(self):
        """Test getting file structure"""
        structure = self.context.get_file_structure()
        
        # Check structure
        self.assertEqual(structure["name"], ".")
        self.assertEqual(structure["type"], "directory")
        
        # Check for src directory
        src_dir = next((child for child in structure["children"] if child["name"] == "src"), None)
        self.assertIsNotNone(src_dir)
        self.assertEqual(src_dir["type"], "directory")

class TestAgentMdParser(unittest.TestCase):
    """Tests for the AgentMdParser class"""
    
    def setUp(self):
        """Set up test environment"""
        self.parser = AgentMdParser()
        
        # Create temporary directory
        self.test_dir = tempfile.mkdtemp()
        
        # Create a test .agent.md file
        self.agent_md_path = Path(self.test_dir) / ".agent.md"
        with open(self.agent_md_path, "w") as f:
            f.write("""# Test Project

## Project Description
A simple test project.

## Architecture
Simple architecture.

## Code Style
Test style.

## Common Commands
- Build: `make build`
- Test: `make test`
- Run: `make run`

## File Descriptions
- `src/main.py`: Main entry point
- `src/utils.py`: Utility functions
- `tests/`: Test directory

## Custom Tools
- `tools/build.sh`: Build script
- `tools/deploy.sh`: Deployment script
""")
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
    
    def test_parse_file(self):
        """Test parsing a .agent.md file"""
        context = self.parser.parse_file(self.agent_md_path)
        
        # Check basic sections
        self.assertEqual(context["project_description"], "A simple test project.")
        self.assertEqual(context["architecture"], "Simple architecture.")
        self.assertEqual(context["code_style"], "Test style.")
        
        # Check common commands
        self.assertIn("Build", context["common_commands"])
        self.assertEqual(context["common_commands"]["Build"], "make build")
        self.assertEqual(context["common_commands"]["Test"], "make test")
        self.assertEqual(context["common_commands"]["Run"], "make run")
        
        # Check file descriptions
        self.assertIn("src/main.py", context["file_descriptions"])
        self.assertEqual(context["file_descriptions"]["src/main.py"], "Main entry point")
        
        # Check custom tools
        self.assertIn("tools/build.sh", context["custom_tools"])
        self.assertEqual(context["custom_tools"]["tools/build.sh"], "Build script")
    
    def test_load_context(self):
        """Test loading context from multiple files"""
        # Create a second .agent.md file
        second_agent_md_path = Path(self.test_dir) / ".agent.local.md"
        with open(second_agent_md_path, "w") as f:
            f.write("""# Local Test Project

## Project Description
Local project settings.

## Architecture
Local architecture.

## Common Commands
- Debug: `make debug`

## File Descriptions
- `local/file.py`: Local file

## Custom Tools
- `tools/local.sh`: Local script
""")
        
        # Load context from both files
        context = self.parser.load_context([self.agent_md_path, second_agent_md_path])
        
        # Check merged sections (second file should override first)
        self.assertEqual(context["project_description"], "Local project settings.")
        self.assertEqual(context["architecture"], "Local architecture.")
        
        # Check merged dictionaries (should include items from both files)
        self.assertIn("Build", context["common_commands"])
        self.assertIn("Debug", context["common_commands"])
        self.assertEqual(context["common_commands"]["Build"], "make build")
        self.assertEqual(context["common_commands"]["Debug"], "make debug")
        
        self.assertIn("src/main.py", context["file_descriptions"])
        self.assertIn("local/file.py", context["file_descriptions"])
        
        self.assertIn("tools/build.sh", context["custom_tools"])
        self.assertIn("tools/local.sh", context["custom_tools"])
    
    def test_create_agent_md(self):
        """Test creating a new .agent.md file"""
        # Create a new file path
        new_file_path = Path(self.test_dir) / "new.agent.md"
        
        # Create file
        result = self.parser.create_agent_md(new_file_path)
        
        # Check result
        self.assertTrue(result)
        self.assertTrue(new_file_path.exists())
        
        # Parse the created file
        context = self.parser.parse_file(new_file_path)
        
        # Check that the template was used
        self.assertIn("project_description", context)
        self.assertIn("common_commands", context)