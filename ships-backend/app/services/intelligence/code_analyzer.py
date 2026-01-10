"""
Code Analyzer - Enhanced tree-sitter Analysis

Provides enhanced file_tree.json with:
- Function/class symbols with signatures
- Import/export tracking
- Complexity metrics

Uses tree-sitter for fast, incremental parsing.
"""

import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("ships.intelligence")

# Try to import tree-sitter
try:
    import tree_sitter_languages
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("[CODE_ANALYZER] tree-sitter-languages not installed")


# Language queries for symbol extraction
SYMBOL_QUERIES = {
    "python": """
    (class_definition name: (identifier) @class_name)
    (function_definition name: (identifier) @function_name)
    (import_statement) @import
    (import_from_statement) @import_from
    """,
    "typescript": """
    (class_declaration name: (type_identifier) @class_name)
    (function_declaration name: (identifier) @function_name)
    (arrow_function) @arrow_function
    (interface_declaration name: (type_identifier) @interface_name)
    (type_alias_declaration name: (type_identifier) @type_name)
    (import_statement) @import
    (export_statement) @export
    """,
    "javascript": """
    (class_declaration name: (identifier) @class_name)
    (function_declaration name: (identifier) @function_name)
    (arrow_function) @arrow_function
    (import_statement) @import
    (export_statement) @export
    """,
}

# Extension to language mapping
EXT_TO_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
}


class CodeAnalyzer:
    """
    Enhanced code analyzer using tree-sitter.
    
    Generates file_tree.json v2.0 with:
    - Symbol-level detail (functions, classes, interfaces)
    - Import/export tracking
    - File hashes for incremental updates
    """
    
    def __init__(self):
        self.parsers: Dict[str, Any] = {}
        self.languages: Dict[str, Any] = {}
        
    def _get_parser(self, language: str):
        """Get or create parser for language."""
        if not TREE_SITTER_AVAILABLE:
            return None, None
            
        if language not in self.parsers:
            try:
                self.parsers[language] = tree_sitter_languages.get_parser(language)
                self.languages[language] = tree_sitter_languages.get_language(language)
            except Exception as e:
                logger.warning(f"[CODE_ANALYZER] Failed to get parser for {language}: {e}")
                return None, None
                
        return self.parsers.get(language), self.languages.get(language)
    
    def _calculate_file_hash(self, content: bytes) -> str:
        """Calculate SHA256 hash of file content."""
        return hashlib.sha256(content).hexdigest()[:16]
    
    def _extract_symbols(self, file_path: Path, content: bytes) -> Dict[str, Any]:
        """Extract symbols from file using tree-sitter."""
        ext = file_path.suffix.lower()
        lang_name = EXT_TO_LANG.get(ext)
        
        if not lang_name:
            return {"functions": [], "classes": [], "imports": [], "exports": []}
        
        parser, language = self._get_parser(lang_name)
        if not parser:
            return {"functions": [], "classes": [], "imports": [], "exports": []}
        
        try:
            tree = parser.parse(content)
            root = tree.root_node
            
            symbols = {
                "functions": [],
                "classes": [],
                "imports": [],
                "exports": []
            }
            
            # Walk the tree
            self._walk_node(root, content, symbols, lang_name)
            
            return symbols
            
        except Exception as e:
            logger.warning(f"[CODE_ANALYZER] Failed to parse {file_path.name}: {e}")
            return {"functions": [], "classes": [], "imports": [], "exports": []}
    
    def _walk_node(self, node, content: bytes, symbols: Dict, lang: str):
        """Recursively walk AST nodes to extract symbols."""
        node_type = node.type
        
        # Python-specific extraction
        if lang == "python":
            if node_type == "function_definition":
                func_info = self._extract_python_function(node, content)
                if func_info:
                    symbols["functions"].append(func_info)
                    
            elif node_type == "class_definition":
                class_info = self._extract_python_class(node, content)
                if class_info:
                    symbols["classes"].append(class_info)
                    
            elif node_type in ("import_statement", "import_from_statement"):
                import_info = self._extract_python_import(node, content)
                if import_info:
                    symbols["imports"].append(import_info)
        
        # TypeScript/JavaScript extraction
        elif lang in ("typescript", "javascript"):
            if node_type in ("function_declaration", "method_definition"):
                func_info = self._extract_ts_function(node, content)
                if func_info:
                    symbols["functions"].append(func_info)
                    
            elif node_type == "class_declaration":
                class_info = self._extract_ts_class(node, content)
                if class_info:
                    symbols["classes"].append(class_info)
                    
            elif node_type == "import_statement":
                import_info = self._extract_ts_import(node, content)
                if import_info:
                    symbols["imports"].append(import_info)
                    
            elif node_type == "export_statement":
                export_info = self._extract_ts_export(node, content)
                if export_info:
                    symbols["exports"].extend(export_info)
        
        # Recurse into children
        for child in node.children:
            self._walk_node(child, content, symbols, lang)
    
    def _extract_python_function(self, node, content: bytes) -> Optional[Dict]:
        """Extract Python function info."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
            
        name = content[name_node.start_byte:name_node.end_byte].decode("utf-8")
        
        # Get parameters
        params = []
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for param in params_node.children:
                if param.type == "identifier":
                    params.append(content[param.start_byte:param.end_byte].decode("utf-8"))
                elif param.type == "typed_parameter":
                    param_name = param.child_by_field_name("name")
                    if param_name:
                        params.append(content[param_name.start_byte:param_name.end_byte].decode("utf-8"))
        
        # Check visibility (starts with _)
        visibility = "private" if name.startswith("_") else "public"
        
        return {
            "name": name,
            "line": node.start_point[0] + 1,
            "visibility": visibility,
            "parameters": params,
        }
    
    def _extract_python_class(self, node, content: bytes) -> Optional[Dict]:
        """Extract Python class info."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
            
        name = content[name_node.start_byte:name_node.end_byte].decode("utf-8")
        
        return {
            "name": name,
            "line": node.start_point[0] + 1,
        }
    
    def _extract_python_import(self, node, content: bytes) -> Optional[Dict]:
        """Extract Python import info."""
        text = content[node.start_byte:node.end_byte].decode("utf-8")
        
        if node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            if module_node:
                module = content[module_node.start_byte:module_node.end_byte].decode("utf-8")
                return {"module": module, "type": "from"}
        else:
            # Regular import
            for child in node.children:
                if child.type == "dotted_name":
                    module = content[child.start_byte:child.end_byte].decode("utf-8")
                    return {"module": module, "type": "import"}
        
        return None
    
    def _extract_ts_function(self, node, content: bytes) -> Optional[Dict]:
        """Extract TypeScript/JavaScript function info."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
            
        name = content[name_node.start_byte:name_node.end_byte].decode("utf-8")
        
        # Get parameters
        params = []
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for param in params_node.children:
                if param.type in ("required_parameter", "optional_parameter", "identifier"):
                    param_name = param.child_by_field_name("pattern") or param
                    if param_name:
                        name_text = content[param_name.start_byte:param_name.end_byte].decode("utf-8")
                        # Include type annotation if present
                        type_node = param.child_by_field_name("type")
                        if type_node:
                            type_text = content[type_node.start_byte:type_node.end_byte].decode("utf-8")
                            params.append(f"{name_text}: {type_text}")
                        else:
                            params.append(name_text)
        
        return {
            "name": name,
            "line": node.start_point[0] + 1,
            "visibility": "export" if self._is_exported(node) else "internal",
            "parameters": params,
        }
    
    def _extract_ts_class(self, node, content: bytes) -> Optional[Dict]:
        """Extract TypeScript/JavaScript class info."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
            
        name = content[name_node.start_byte:name_node.end_byte].decode("utf-8")
        
        return {
            "name": name,
            "line": node.start_point[0] + 1,
            "visibility": "export" if self._is_exported(node) else "internal",
        }
    
    def _extract_ts_import(self, node, content: bytes) -> Optional[Dict]:
        """Extract TypeScript/JavaScript import info."""
        # Find the source (module path)
        source_node = node.child_by_field_name("source")
        if source_node:
            module = content[source_node.start_byte:source_node.end_byte].decode("utf-8")
            # Remove quotes
            module = module.strip("'\"")
            
            # Get imported items
            items = []
            for child in node.children:
                if child.type == "import_clause":
                    for item in child.children:
                        if item.type == "identifier":
                            items.append(content[item.start_byte:item.end_byte].decode("utf-8"))
                        elif item.type == "named_imports":
                            for spec in item.children:
                                if spec.type == "import_specifier":
                                    name = spec.child_by_field_name("name")
                                    if name:
                                        items.append(content[name.start_byte:name.end_byte].decode("utf-8"))
            
            return {"module": module, "items": items}
        
        return None
    
    def _extract_ts_export(self, node, content: bytes) -> List[str]:
        """Extract TypeScript/JavaScript export names."""
        exports = []
        
        for child in node.children:
            if child.type == "export_clause":
                for spec in child.children:
                    if spec.type == "export_specifier":
                        name = spec.child_by_field_name("name")
                        if name:
                            exports.append(content[name.start_byte:name.end_byte].decode("utf-8"))
            elif child.type in ("function_declaration", "class_declaration"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    exports.append(content[name_node.start_byte:name_node.end_byte].decode("utf-8"))
        
        return exports
    
    def _is_exported(self, node) -> bool:
        """Check if a node is exported."""
        parent = node.parent
        if parent and parent.type == "export_statement":
            return True
        return False
    
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single file and return enhanced metadata."""
        try:
            content = file_path.read_bytes()
            
            result = {
                "path": str(file_path),
                "size": len(content),
                "hash": self._calculate_file_hash(content),
                "language": EXT_TO_LANG.get(file_path.suffix.lower(), "unknown"),
                "symbols": self._extract_symbols(file_path, content),
            }
            
            return result
            
        except Exception as e:
            logger.error(f"[CODE_ANALYZER] Error analyzing {file_path}: {e}")
            return {
                "path": str(file_path),
                "error": str(e)
            }
    
    def analyze_project(self, project_path: str, max_depth: int = 5) -> Dict[str, Any]:
        """
        Analyze entire project and generate file_tree.json v2.0.
        
        Args:
            project_path: Root directory to analyze
            max_depth: Maximum directory depth
            
        Returns:
            Dict with version, files, and metadata
        """
        root = Path(project_path)
        
        if not root.exists():
            return {"success": False, "error": f"Path not found: {project_path}"}
        
        ignore_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "dist", "build", ".next", ".ships", "coverage"
        }
        
        files = {}
        file_count = 0
        
        for path in root.rglob("*"):
            # Skip ignored directories
            if any(part in ignore_dirs or part.startswith(".") for part in path.parts):
                continue
            
            # Limit depth
            try:
                rel_path = path.relative_to(root)
                if len(rel_path.parts) > max_depth:
                    continue
            except ValueError:
                continue
            
            # Only analyze code files
            if path.is_file() and path.suffix.lower() in EXT_TO_LANG:
                file_info = self.analyze_file(path)
                files[str(rel_path)] = file_info
                file_count += 1
        
        logger.info(f"[CODE_ANALYZER] Analyzed {file_count} files in {root}")
        
        return {
            "version": "2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "files": files,
            "stats": {
                "total_files": file_count,
            }
        }
    
    def save_artifact(self, project_path: str, output_path: Optional[str] = None) -> str:
        """Analyze project and save to file_tree.json."""
        import json
        
        result = self.analyze_project(project_path)
        
        if not result.get("success"):
            raise ValueError(result.get("error", "Unknown error"))
        
        # Default to .ships/file_tree.json
        if not output_path:
            output_path = Path(project_path) / ".ships" / "file_tree.json"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"[CODE_ANALYZER] Saved file_tree.json to {output_path}")
        
        return str(output_path)
