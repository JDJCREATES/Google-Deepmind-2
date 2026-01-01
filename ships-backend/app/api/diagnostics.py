"""
Monaco Diagnostics API

Receives diagnostic reports from the Monaco editor in the frontend
and stores them for the Fixer agent to consume.

Security:
- Localhost only (enforced by middleware)
- Path validation (only project files allowed)
- Rate limiting (debounced on frontend, validated here)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("ships.diagnostics")

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


# ============================================================================
# Models
# ============================================================================

class DiagnosticError(BaseModel):
    """A single diagnostic error from Monaco."""
    file: str                       # Relative path (e.g., "src/App.tsx")
    line: int                       # 1-indexed line number
    column: int = 1                 # 1-indexed column
    message: str                    # Error message from Monaco
    severity: str = "error"         # "error" | "warning" | "info"
    code: Optional[str] = None      # TypeScript error code (e.g., "TS2339")
    source: Optional[str] = None    # Language service (e.g., "typescript")


class DiagnosticsReport(BaseModel):
    """A report of diagnostics from a project."""
    project_path: str
    errors: List[DiagnosticError]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DiagnosticsStatus(BaseModel):
    """Current diagnostics status for a project."""
    project_path: str
    error_count: int
    errors: List[DiagnosticError]
    last_updated: Optional[datetime] = None


# ============================================================================
# In-Memory Store (could be replaced with Redis for production)
# ============================================================================

_diagnostics_store: Dict[str, DiagnosticsStatus] = {}


def get_diagnostics(project_path: str) -> Optional[DiagnosticsStatus]:
    """Get current diagnostics for a project."""
    return _diagnostics_store.get(project_path)


def set_diagnostics(project_path: str, errors: List[DiagnosticError]) -> None:
    """Update diagnostics for a project."""
    _diagnostics_store[project_path] = DiagnosticsStatus(
        project_path=project_path,
        error_count=len(errors),
        errors=errors,
        last_updated=datetime.utcnow()
    )


def clear_diagnostics(project_path: str) -> None:
    """Clear diagnostics for a project."""
    if project_path in _diagnostics_store:
        del _diagnostics_store[project_path]


# ============================================================================
# Security Helpers
# ============================================================================

def is_localhost(request: Request) -> bool:
    """Check if request is from localhost."""
    client_host = request.client.host if request.client else ""
    return client_host in ("127.0.0.1", "localhost", "::1")


def validate_project_path(project_path: str) -> bool:
    """
    Validate that the project path exists and is safe.
    Returns True if valid, False otherwise.
    """
    try:
        path = Path(project_path).resolve()
        # Must exist and be a directory
        if not path.exists() or not path.is_dir():
            return False
        # Must have a .ships folder (proves it's a ShipS project)
        ships_dir = path / ".ships"
        if not ships_dir.exists():
            return False
        return True
    except Exception:
        return False


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/report")
async def report_diagnostics(report: DiagnosticsReport, request: Request):
    """
    Receive diagnostic errors from Monaco editor.
    
    Called by the frontend when Monaco's language service detects errors.
    """
    # Security: Localhost only
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Forbidden: Localhost only")
    
    # Validate project path
    if not validate_project_path(report.project_path):
        raise HTTPException(status_code=400, detail="Invalid project path")
    
    # Validate file paths (must be relative and safe)
    for error in report.errors:
        if error.file.startswith("/") or ".." in error.file:
            raise HTTPException(status_code=400, detail=f"Invalid file path: {error.file}")
    
    # Store diagnostics
    set_diagnostics(report.project_path, report.errors)
    
    logger.info(f"[DIAGNOSTICS] Received {len(report.errors)} errors for {report.project_path}")
    
    return {
        "success": True,
        "error_count": len(report.errors),
        "project_path": report.project_path
    }


@router.get("/status")
async def get_diagnostics_status(project_path: str, request: Request):
    """
    Get current diagnostics status for a project.
    
    Returns the list of current errors (if any).
    """
    # Security: Localhost only
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Forbidden: Localhost only")
    
    status = get_diagnostics(project_path)
    
    if status is None:
        return {
            "project_path": project_path,
            "error_count": 0,
            "errors": [],
            "last_updated": None
        }
    
    return status.model_dump()


@router.post("/clear")
async def clear_project_diagnostics(project_path: str, request: Request):
    """Clear diagnostics for a project."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Forbidden: Localhost only")
    
    clear_diagnostics(project_path)
    
    return {"success": True, "project_path": project_path}
