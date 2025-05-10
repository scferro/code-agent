"""Implementation of .agent.md file parsing and management"""
from pathlib import Path
import re
from typing import List, Dict, Any, Optional

class AgentMdParser:
    """Parser for .agent.md files"""
    
    def __init__(self):
        self.section_patterns = {
            "project_description": r"## Project Description\s+(.+?)(?=##|$)",
            "architecture": r"## Architecture\s+(.+?)(?=##|$)",
            "code_style": r"## Code Style\s+(.+?)(?=##|$)",
            "common_commands": r"## Common Commands\s+(.+?)(?=##|$)",
            "file_descriptions": r"## File Descriptions\s+(.+?)(?=##|$)",
            "custom_tools": r"## Custom Tools\s+(.+?)(?=##|$)"
        }
    
    def load_context(self, file_paths: List[Path]) -> Dict[str, Any]:
        """Load and merge context from multiple .agent.md files"""
        merged_context = {}
        
        for file_path in file_paths:
            if file_path.exists():
                file_context = self.parse_file(file_path)
                self._merge_into(merged_context, file_context)
        
        return merged_context
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse a single .agent.md file"""
        try:
            content = file_path.read_text()
            context = {}
            
            # Extract sections using regex
            for section_name, pattern in self.section_patterns.items():
                matches = re.search(pattern, content, re.DOTALL)
                if matches:
                    raw_content = matches.group(1).strip()
                    
                    # Process special sections
                    if section_name == "common_commands":
                        context[section_name] = self._parse_commands_section(raw_content)
                    elif section_name == "file_descriptions":
                        context[section_name] = self._parse_file_descriptions(raw_content)
                    elif section_name == "custom_tools":
                        context[section_name] = self._parse_custom_tools(raw_content)
                    else:
                        context[section_name] = raw_content
                else:
                    context[section_name] = ""
            
            return context
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return {}
    
    def _parse_commands_section(self, content: str) -> Dict[str, str]:
        """Parse the common commands section into a dictionary"""
        commands = {}
        lines = content.split("\n")
        
        for line in lines:
            # Look for patterns like "- Build: `command`" or "* Run: `command`"
            match = re.search(r"[-*]\s+([^:]+):\s+`([^`]+)`", line)
            if match:
                command_name = match.group(1).strip()
                command_value = match.group(2).strip()
                commands[command_name] = command_value
        
        return commands
    
    def _parse_file_descriptions(self, content: str) -> Dict[str, str]:
        """Parse file descriptions section into a dictionary"""
        descriptions = {}
        lines = content.split("\n")
        
        for line in lines:
            # Look for patterns like "- `file/path.ext`: Description"
            match = re.search(r"[-*]\s+`([^`]+)`:\s+(.+)$", line)
            if match:
                file_path = match.group(1).strip()
                description = match.group(2).strip()
                descriptions[file_path] = description
        
        return descriptions
    
    def _parse_custom_tools(self, content: str) -> Dict[str, str]:
        """Parse custom tools section into a dictionary"""
        tools = {}
        lines = content.split("\n")
        
        for line in lines:
            # Look for patterns like "- `tool_name.ext`: Description"
            match = re.search(r"[-*]\s+`([^`]+)`:\s+(.+)$", line)
            if match:
                tool_name = match.group(1).strip()
                description = match.group(2).strip()
                tools[tool_name] = description
        
        return tools
    
    def _merge_into(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge source context into target context, with source taking precedence"""
        for key, value in source.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target[key], dict):
                # For dictionaries, merge them
                target[key].update(value)
            elif value:  # Only override if value is not empty
                target[key] = value
    
    def generate_template(self) -> str:
        """Generate a template .agent.md file"""
        return """# Project Configuration for CodeAgent

## Project Description
Brief description of what this project does.

## Architecture
Overview of the project's architecture and main components.

## Code Style
Coding conventions and style guidelines for this project.

## Common Commands
Commands frequently used in this project:

- Build: `command to build the project`
- Test: `command to run tests`
- Run: `command to run the project`

## File Descriptions
Key files and directories in this project:

- `src/`: Source code directory
- `tests/`: Test directory
- `README.md`: Project documentation

## Custom Tools
Custom tools or scripts specific to this project:

- `scripts/build.sh`: Build script
"""

    def create_agent_md(self, path: Path, overwrite: bool = False) -> bool:
        """Create a new .agent.md file with the template"""
        if path.exists() and not overwrite:
            return False
        
        template = self.generate_template()
        path.write_text(template)
        return True