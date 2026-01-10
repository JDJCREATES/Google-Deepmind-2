"""
LLM Context Builder

Builds optimized context for LLM prompts from artifacts.
Prevents hallucinations by providing:
- Valid function signatures
- Valid import paths
- Architecture constraints
- Code patterns
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass

logger = logging.getLogger("ships.context")


@dataclass
class ContextRequest:
    """Request for LLM context."""
    task_type: Literal["planning", "coding", "fixing", "refactoring"]
    scope: List[str]  # Files or symbols to focus on
    max_tokens: int = 8000
    include_architecture: bool = True
    include_patterns: bool = True
    include_examples: bool = True


class LLMContextBuilder:
    """
    Builds minimal, accurate context for LLM prompts.
    
    Uses artifacts to provide:
    - Valid function signatures (prevents inventing functions)
    - Valid imports (prevents import hallucinations)
    - Architecture constraints (prevents layer violations)
    - Code patterns (maintains consistency)
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.ships_dir = self.project_path / ".ships"
        self.artifacts_cache: Dict[str, Any] = {}
    
    def _load_artifact(self, name: str) -> Optional[Dict]:
        """Load artifact from .ships directory."""
        if name in self.artifacts_cache:
            return self.artifacts_cache[name]
        
        artifact_path = self.ships_dir / name
        if not artifact_path.exists():
            return None
        
        try:
            with open(artifact_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.artifacts_cache[name] = data
                return data
        except Exception as e:
            logger.warning(f"[CONTEXT] Failed to load {name}: {e}")
            return None
    
    def build(self, request: ContextRequest) -> str:
        """
        Build optimized context for LLM.
        
        Args:
            request: ContextRequest with task_type and scope
            
        Returns:
            Formatted context string for LLM prompt
        """
        context_parts = []
        
        # 1. Task-specific header
        context_parts.append(self._build_header(request))
        
        # 2. Valid functions in scope
        context_parts.append(self._build_function_context(request.scope))
        
        # 3. Valid imports
        context_parts.append(self._build_import_context(request.scope))
        
        # 4. Architecture constraints
        if request.include_architecture:
            arch_context = self._build_architecture_context(request.scope)
            if arch_context:
                context_parts.append(arch_context)
        
        # 5. Code patterns
        if request.include_patterns:
            pattern_context = self._build_pattern_context()
            if pattern_context:
                context_parts.append(pattern_context)
        
        # 6. Security warnings
        security_context = self._build_security_context()
        if security_context:
            context_parts.append(security_context)
        
        # Combine and truncate
        full_context = "\n\n".join(filter(None, context_parts))
        return self._truncate_to_tokens(full_context, request.max_tokens)
    
    def _build_header(self, request: ContextRequest) -> str:
        """Build task-specific header."""
        headers = {
            "planning": "## Planning Context\nYou are planning implementation for:",
            "coding": "## Coding Context\nYou are implementing code in:",
            "fixing": "## Fix Context\nYou are fixing an issue in:",
            "refactoring": "## Refactoring Context\nYou are refactoring:"
        }
        
        header = headers.get(request.task_type, "## Context")
        scope_list = ", ".join(f"`{s}`" for s in request.scope[:5])
        
        return f"{header}\nScope: {scope_list}"
    
    def _build_function_context(self, scope: List[str]) -> str:
        """Build valid function signatures for scope."""
        file_tree = self._load_artifact("file_tree.json")
        call_graph = self._load_artifact("function_call_graph.json")
        
        if not file_tree:
            return ""
        
        functions = []
        files = file_tree.get("files", {})
        
        for file_path in scope:
            if file_path in files:
                file_data = files[file_path]
                symbols = file_data.get("symbols", {})
                
                for func in symbols.get("functions", []):
                    name = func.get("name", "")
                    params = ", ".join(func.get("parameters", []))
                    visibility = func.get("visibility", "")
                    
                    sig = f"  {'[export] ' if visibility == 'export' else ''}{name}({params})"
                    functions.append(sig)
        
        if not functions:
            return ""
        
        return f"### Valid Functions\nThese are the ONLY functions you can call:\n" + "\n".join(functions[:20])
    
    def _build_import_context(self, scope: List[str]) -> str:
        """Build valid imports for scope files."""
        dep_graph = self._load_artifact("dependency_graph.json")
        file_tree = self._load_artifact("file_tree.json")
        
        if not file_tree:
            return ""
        
        imports = []
        files = file_tree.get("files", {})
        
        for file_path in scope:
            if file_path in files:
                file_data = files[file_path]
                symbols = file_data.get("symbols", {})
                
                for imp in symbols.get("imports", []):
                    module = imp.get("module", "")
                    items = imp.get("items", [])
                    
                    if items:
                        imp_str = f"  from '{module}': {', '.join(items)}"
                    else:
                        imp_str = f"  import '{module}'"
                    
                    imports.append(imp_str)
        
        if not imports:
            return ""
        
        return f"### Valid Imports\nThese are the ONLY modules you can import:\n" + "\n".join(imports[:15])
    
    def _build_architecture_context(self, scope: List[str]) -> str:
        """Build architecture constraints."""
        # Try to infer layer from file paths
        layers = {
            "routes": "presentation",
            "controllers": "presentation",
            "services": "business_logic",
            "models": "data_access",
            "repositories": "data_access",
            "components": "presentation",
            "hooks": "presentation",
            "utils": "utility",
            "lib": "utility"
        }
        
        detected_layers = []
        for file_path in scope:
            for pattern, layer in layers.items():
                if pattern in file_path.lower():
                    detected_layers.append(layer)
                    break
        
        if not detected_layers:
            return ""
        
        primary_layer = max(set(detected_layers), key=detected_layers.count)
        
        allowed = {
            "presentation": ["business_logic", "utility"],
            "business_logic": ["data_access", "utility"],
            "data_access": ["utility"],
            "utility": []
        }
        
        allowed_deps = allowed.get(primary_layer, [])
        
        return f"""### Architecture Constraints
Current layer: {primary_layer}
Allowed dependencies: {', '.join(allowed_deps) if allowed_deps else 'none (utility layer)'}
FORBIDDEN: Skipping layers (e.g., presentation -> data_access directly)"""
    
    def _build_pattern_context(self) -> str:
        """Build code pattern context."""
        pattern_registry = self._load_artifact("pattern_registry.json")
        
        if not pattern_registry:
            # Return reasonable defaults
            return """### Code Patterns
- Error handling: try-catch with logging
- Async: async/await (not .then())
- Naming: camelCase for functions, PascalCase for classes"""
        
        patterns = []
        
        naming = pattern_registry.get("naming_conventions", {})
        if naming:
            patterns.append(f"Naming: {naming.get('functions', 'camelCase')} functions, {naming.get('classes', 'PascalCase')} classes")
        
        async_pattern = pattern_registry.get("async_patterns", {})
        if async_pattern:
            patterns.append(f"Async: {async_pattern.get('pattern', 'async/await')}")
        
        error_pattern = pattern_registry.get("detected_patterns", {}).get("error_handling", {})
        if error_pattern:
            patterns.append(f"Errors: {error_pattern.get('pattern', 'try-catch')}")
        
        if not patterns:
            return ""
        
        return "### Code Patterns\n" + "\n".join(f"- {p}" for p in patterns)
    
    def _build_security_context(self) -> str:
        """Build security warnings if issues exist."""
        security = self._load_artifact("security_report.json")
        
        if not security:
            return ""
        
        vulns = security.get("vulnerabilities", {})
        critical = vulns.get("critical", [])
        high = vulns.get("high", [])
        
        if not critical and not high:
            return ""
        
        warnings = []
        for vuln in critical[:3] + high[:3]:
            pkg = vuln.get("package", "unknown")
            warnings.append(f"  ⚠️ {pkg}: {vuln.get('severity', 'high')}")
        
        return "### Security Warnings\n" + "\n".join(warnings)
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to approximate token limit."""
        # Rough estimate: 4 chars per token
        max_chars = max_tokens * 4
        
        if len(text) <= max_chars:
            return text
        
        return text[:max_chars] + "\n\n[Context truncated...]"
    
    def build_for_coding(self, files: List[str]) -> str:
        """Convenience method for coding context."""
        return self.build(ContextRequest(
            task_type="coding",
            scope=files,
            include_architecture=True,
            include_patterns=True
        ))
    
    def build_for_fixing(self, files: List[str], error: str = "") -> str:
        """Convenience method for fixing context."""
        context = self.build(ContextRequest(
            task_type="fixing",
            scope=files,
            include_architecture=True,
            include_patterns=True
        ))
        
        if error:
            context = f"## Error\n```\n{error[:500]}\n```\n\n{context}"
        
        return context
    
    def build_for_planning(self) -> str:
        """Convenience method for planning context."""
        # Get all files for high-level overview
        file_tree = self._load_artifact("file_tree.json")
        files = list(file_tree.get("files", {}).keys())[:20] if file_tree else []
        
        return self.build(ContextRequest(
            task_type="planning",
            scope=files,
            include_architecture=True,
            include_patterns=False,
            max_tokens=4000
        ))
