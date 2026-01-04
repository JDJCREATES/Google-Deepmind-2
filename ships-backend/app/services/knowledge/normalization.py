"""
Error normalization for knowledge capture.

Strips variable parts from error messages to enable deduplication
and pattern matching across different projects.
"""

import re
import hashlib
from typing import Optional


def normalize_error(error: str) -> str:
    """
    Normalize error message for storage and deduplication.
    
    Removes project-specific details while preserving the error pattern.
    
    Args:
        error: Raw error message
        
    Returns:
        Normalized error signature
    """
    normalized = error
    
    # Remove absolute file paths (Windows and Unix)
    normalized = re.sub(r'[A-Za-z]:\\[\w\\.-]+\.(py|js|ts|tsx|jsx|css|html)', '<FILE>', normalized)
    normalized = re.sub(r'/[\w/.-]+\.(py|js|ts|tsx|jsx|css|html)', '<FILE>', normalized)
    
    # Remove line and column numbers
    normalized = re.sub(r'line \d+', 'line N', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'column \d+', 'col N', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r':\d+:\d+', ':N:N', normalized)
    
    # Remove UUIDs
    normalized = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '<UUID>', normalized, flags=re.IGNORECASE)
    
    # Remove hex addresses
    normalized = re.sub(r'0x[a-f0-9]+', '<ADDR>', normalized, flags=re.IGNORECASE)
    
    # Remove specific variable names in quotes (but keep quoted strings context)
    normalized = re.sub(r"'[a-zA-Z_][a-zA-Z0-9_]*'", "'<VAR>'", normalized)
    normalized = re.sub(r'"[a-zA-Z_][a-zA-Z0-9_]*"', '"<VAR>"', normalized)
    
    # Remove package versions
    normalized = re.sub(r'@[\d.]+', '@X.X', normalized)
    normalized = re.sub(r'version \d+\.\d+\.?\d*', 'version X.X', normalized)
    
    # Collapse whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Truncate to reasonable length
    if len(normalized) > 500:
        normalized = normalized[:500]
    
    return normalized.strip()


def generate_error_signature(error: str) -> str:
    """
    Generate a short signature for error deduplication.
    
    Creates a hash-based signature that's stable across projects.
    
    Args:
        error: Raw or normalized error message
        
    Returns:
        Short signature string
    """
    normalized = normalize_error(error)
    # Create hash for efficient comparison
    hash_val = hashlib.md5(normalized.encode()).hexdigest()[:12]
    
    # Extract error type for readability
    error_type = _extract_error_type(normalized)
    
    return f"{error_type}:{hash_val}"


def _extract_error_type(error: str) -> str:
    """Extract the primary error type from message."""
    # Common Python error types
    python_errors = [
        'ModuleNotFoundError', 'ImportError', 'SyntaxError', 'TypeError',
        'ValueError', 'KeyError', 'AttributeError', 'NameError', 'IndexError'
    ]
    for err_type in python_errors:
        if err_type in error:
            return err_type
    
    # Common JavaScript/TypeScript errors
    js_errors = [
        'ReferenceError', 'TypeError', 'SyntaxError', 'RangeError'
    ]
    for err_type in js_errors:
        if err_type in error:
            return f"JS{err_type}"
    
    # Build tool errors
    if 'ENOENT' in error or 'no such file' in error.lower():
        return 'FileNotFound'
    if 'cannot find module' in error.lower():
        return 'ModuleNotFound'
    if 'compilation failed' in error.lower() or 'build failed' in error.lower():
        return 'BuildError'
    if 'CORS' in error.upper():
        return 'CORSError'
    
    return 'UnknownError'


def extract_tech_stack(context: dict) -> str:
    """
    Extract compact tech stack identifier from project context.
    
    Args:
        context: Project context dict with files, dependencies, etc.
        
    Returns:
        Compact stack string like "react+fastapi+postgres"
    """
    components = []
    
    # Frontend detection
    files = context.get('files', [])
    deps = context.get('dependencies', {})
    
    if any('react' in str(d).lower() for d in deps.get('frontend', [])):
        components.append('react')
    elif any('vue' in str(d).lower() for d in deps.get('frontend', [])):
        components.append('vue')
    elif any('.tsx' in f or '.jsx' in f for f in files):
        components.append('react')
    
    # Backend detection
    if any('fastapi' in str(d).lower() for d in deps.get('backend', [])):
        components.append('fastapi')
    elif any('flask' in str(d).lower() for d in deps.get('backend', [])):
        components.append('flask')
    elif any('express' in str(d).lower() for d in deps.get('backend', [])):
        components.append('express')
    
    # Database detection
    if any('postgres' in str(d).lower() or 'pg' in str(d).lower() for d in deps.get('backend', [])):
        components.append('postgres')
    elif any('mongodb' in str(d).lower() for d in deps.get('backend', [])):
        components.append('mongo')
    elif any('sqlite' in str(d).lower() for d in deps.get('backend', [])):
        components.append('sqlite')
    
    return '+'.join(components) if components else 'unknown'


def extract_solution_pattern(code: str) -> str:
    """
    Convert literal code to a reusable pattern.
    
    Abstracts specific names while preserving structure.
    
    Args:
        code: Literal code diff or snippet
        
    Returns:
        Abstracted pattern
    """
    pattern = code
    
    # Replace function names
    pattern = re.sub(r'def ([a-z_][a-z0-9_]*)\(', r'def <func>(', pattern)
    pattern = re.sub(r'function ([a-zA-Z_][a-zA-Z0-9_]*)\(', r'function <func>(', pattern)
    pattern = re.sub(r'const ([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\(', r'const <func> = (', pattern)
    
    # Replace class names
    pattern = re.sub(r'class ([A-Z][a-zA-Z0-9_]*)', r'class <Class>', pattern)
    
    # Replace variable names in assignments (simple cases)
    pattern = re.sub(r'^\s*(let|const|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=', r'\1 <var> =', pattern, flags=re.MULTILINE)
    
    # Keep string content but mark as variable
    pattern = re.sub(r'["\'][^"\']{20,}["\']', '"<string>"', pattern)
    
    return pattern
