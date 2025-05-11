"""Code analysis tools"""
from langchain.tools import tool
import re
from typing import Any

def get_code_tools(project_context):
    """Get code analysis tools"""
    
    @tool
    def analyze_code(file_path):
        """Analyze code in a file to extract structure, functions, classes, etc."""
        try:
            full_path = project_context.project_dir / file_path
            
            # Check if file exists
            if not full_path.exists():
                return f"Error: File '{file_path}' does not exist"
                
            if not full_path.is_file():
                return f"Error: '{file_path}' is not a file"
            
            # Read file
            content = full_path.read_text(errors='ignore')
            
            # Determine file type
            extension = full_path.suffix.lower()
            
            if extension == '.py':
                analysis = _analyze_python(content)
            elif extension in ['.js', '.jsx', '.ts', '.tsx']:
                analysis = _analyze_javascript(content)
            elif extension in ['.java']:
                analysis = _analyze_java(content)
            else:
                analysis = _analyze_generic(content)
            
            # Track that this file has been explored
            project_context.track_file_exploration(file_path)
            
            # Format output
            output = [f"Code Analysis for: {file_path}"]
            
            # Add imports
            if analysis.get("imports"):
                output.append("\nImports:")
                for imp in analysis["imports"]:
                    output.append(f"- {imp}")
            
            # Add functions
            if analysis.get("functions"):
                output.append("\nFunctions:")
                for func in analysis["functions"]:
                    output.append(f"- {func}")
            
            # Add classes
            if analysis.get("classes"):
                output.append("\nClasses:")
                for cls in analysis["classes"]:
                    output.append(f"- {cls}")
            
            # Add variables
            if analysis.get("variables"):
                output.append("\nGlobal Variables:")
                for var in analysis["variables"]:
                    output.append(f"- {var}")
            
            return "\n".join(output)
        except Exception as e:
            return f"Error analyzing code: {e}"
    
    @tool
    def get_dependencies(file_path):
        """Get dependencies and imports for a file."""
        try:
            full_path = project_context.project_dir / file_path
            
            # Check if file exists
            if not full_path.exists():
                return f"Error: File '{file_path}' does not exist"
                
            if not full_path.is_file():
                return f"Error: '{file_path}' is not a file"
            
            # Read file
            content = full_path.read_text(errors='ignore')
            
            # Determine file type
            extension = full_path.suffix.lower()
            imports = []
            
            if extension == '.py':
                imports = _extract_python_imports(content)
            elif extension in ['.js', '.jsx', '.ts', '.tsx']:
                imports = _extract_js_imports(content)
            elif extension in ['.java']:
                imports = _extract_java_imports(content)
            else:
                imports = []
            
            # Track that this file has been explored
            project_context.track_file_exploration(file_path)
            
            # Format output
            if not imports:
                return f"No dependencies found in {file_path}"
            
            output = [f"Dependencies for {file_path}:"]
            for imp in imports:
                output.append(f"- {imp}")
            
            return "\n".join(output)
        except Exception as e:
            return f"Error getting dependencies: {e}"
    
    # Helper functions for code analysis
    def _analyze_python(content):
        """Analyze Python code"""
        analysis = {
            "imports": [],
            "functions": [],
            "classes": [],
            "variables": []
        }
        
        # Extract imports
        import_pattern = re.compile(r'^(?:from|import)\s+([^\s;]+)', re.MULTILINE)
        for match in import_pattern.finditer(content):
            analysis["imports"].append(match.group(0))
        
        # Extract function definitions
        function_pattern = re.compile(r'^def\s+([^\s(]+)', re.MULTILINE)
        for match in function_pattern.finditer(content):
            analysis["functions"].append(match.group(1))
        
        # Extract class definitions
        class_pattern = re.compile(r'^class\s+([^\s:(]+)', re.MULTILINE)
        for match in class_pattern.finditer(content):
            analysis["classes"].append(match.group(1))
        
        # Extract global variables (rough estimation)
        var_pattern = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*=', re.MULTILINE)
        for match in var_pattern.finditer(content):
            analysis["variables"].append(match.group(1))
        
        return analysis
    
    def _analyze_javascript(content):
        """Analyze JavaScript/TypeScript code"""
        analysis = {
            "imports": [],
            "functions": [],
            "classes": [],
            "variables": []
        }
        
        # Extract imports
        import_pattern = re.compile(r'(?:import|require)\s*\(?[\'"]([^\'"]+)[\'"]', re.MULTILINE)
        for match in import_pattern.finditer(content):
            analysis["imports"].append(match.group(0))
        
        # Extract function definitions
        function_pattern = re.compile(r'(?:function|const|let|var)\s+([^\s(=]+)(?:\s*=\s*(?:function|\([^)]*\)\s*=>|\([^)]*\)\s*\{))?', re.MULTILINE)
        for match in function_pattern.finditer(content):
            name = match.group(1)
            if name not in analysis["imports"]:  # Avoid duplicates
                analysis["functions"].append(name)
        
        # Extract class definitions
        class_pattern = re.compile(r'class\s+([^\s{]+)', re.MULTILINE)
        for match in class_pattern.finditer(content):
            analysis["classes"].append(match.group(1))
        
        # Extract global variables (rough estimation)
        var_pattern = re.compile(r'^(?:const|let|var)\s+([A-Z_][A-Z0-9_]*)\s*=', re.MULTILINE)
        for match in var_pattern.finditer(content):
            var_name = match.group(1)
            if var_name not in analysis["functions"]:  # Avoid duplicates
                analysis["variables"].append(var_name)
        
        return analysis
    
    def _analyze_java(content):
        """Analyze Java code"""
        analysis = {
            "imports": [],
            "functions": [],
            "classes": [],
            "variables": []
        }
        
        # Extract imports
        import_pattern = re.compile(r'^import\s+([^;]+);', re.MULTILINE)
        for match in import_pattern.finditer(content):
            analysis["imports"].append(match.group(0))
        
        # Extract class definitions
        class_pattern = re.compile(r'(?:public|private|protected)?\s*class\s+([^\s{]+)', re.MULTILINE)
        for match in class_pattern.finditer(content):
            analysis["classes"].append(match.group(1))
        
        # Extract method definitions (rough estimation)
        method_pattern = re.compile(r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{', re.MULTILINE)
        for match in method_pattern.finditer(content):
            analysis["functions"].append(match.group(1))
        
        # Extract constants (rough estimation)
        const_pattern = re.compile(r'(?:public|private|protected)?\s*static\s*final\s*\w+\s+([A-Z_][A-Z0-9_]*)\s*=', re.MULTILINE)
        for match in const_pattern.finditer(content):
            analysis["variables"].append(match.group(1))
        
        return analysis
    
    def _analyze_generic(content):
        """Generic code analysis"""
        analysis = {
            "imports": [],
            "functions": [],
            "classes": [],
            "variables": []
        }
        
        # Simple line count and word count
        lines = content.split('\n')
        analysis["line_count"] = len(lines)
        analysis["word_count"] = len(content.split())
        
        return analysis
    
    def _extract_python_imports(content):
        """Extract imports from Python code"""
        imports = []
        
        # From imports
        from_pattern = re.compile(r'^from\s+([^\s;]+)\s+import\s+([^#\n]+)', re.MULTILINE)
        for match in from_pattern.finditer(content):
            module = match.group(1)
            items = match.group(2).strip()
            imports.append(f"from {module} import {items}")
        
        # Direct imports
        import_pattern = re.compile(r'^import\s+([^#\n]+)', re.MULTILINE)
        for match in import_pattern.finditer(content):
            items = match.group(1).strip()
            imports.append(f"import {items}")
        
        return imports
    
    def _extract_js_imports(content):
        """Extract imports from JavaScript/TypeScript code"""
        imports = []
        
        # ES6 imports
        es6_pattern = re.compile(r'import\s+(?:{[^}]+}|[^{}\s;]+)\s+from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE)
        for match in es6_pattern.finditer(content):
            imports.append(f"import from '{match.group(1)}'")
        
        # Require imports
        require_pattern = re.compile(r'(?:const|let|var)\s+(?:\w+|\{[^}]+\})\s*=\s*require\([\'"]([^\'"]+)[\'"]\)', re.MULTILINE)
        for match in require_pattern.finditer(content):
            imports.append(f"require('{match.group(1)}')")
        
        return imports
    
    def _extract_java_imports(content):
        """Extract imports from Java code"""
        imports = []
        
        # Java imports
        import_pattern = re.compile(r'^import\s+([^;]+);', re.MULTILINE)
        for match in import_pattern.finditer(content):
            imports.append(match.group(1))
        
        return imports
    
    return [analyze_code, get_dependencies]