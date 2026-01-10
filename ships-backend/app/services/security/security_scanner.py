"""
Security Scanner

Provides vulnerability scanning using:
- npm audit (Node.js)
- pip-audit (Python)
- depcheck (unused dependencies)

Generates security_report.json artifact.
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("ships.intelligence")


class SecurityScanner:
    """
    Security vulnerability scanner for projects.
    
    Uses npm audit and pip-audit for CVE detection,
    depcheck for unused dependencies.
    """
    
    def scan_project(self, project_path: str) -> Dict[str, Any]:
        """
        Scan project for security vulnerabilities.
        
        Args:
            project_path: Root directory of the project
            
        Returns:
            Security report with vulnerabilities and issues
        """
        root = Path(project_path)
        
        vulnerabilities = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": []
        }
        
        unused_dependencies = []
        outdated_dependencies = []
        code_issues = {
            "hardcoded_secrets": [],
            "sql_injection": [],
            "xss": []
        }
        
        # Check for Node.js project
        if (root / "package.json").exists():
            npm_result = self._run_npm_audit(root)
            if npm_result.get("success"):
                self._merge_vulnerabilities(vulnerabilities, npm_result.get("vulnerabilities", {}))
            
            depcheck_result = self._run_depcheck(root)
            if depcheck_result.get("success"):
                unused_dependencies.extend(depcheck_result.get("unused", []))
        
        # Check for Python project
        if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
            pip_result = self._run_pip_audit(root)
            if pip_result.get("success"):
                self._merge_vulnerabilities(vulnerabilities, pip_result.get("vulnerabilities", {}))
        
        # Basic secret detection
        code_issues["hardcoded_secrets"] = self._scan_for_secrets(root)
        
        total_vulns = sum(len(v) for v in vulnerabilities.values())
        
        return {
            "version": "2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "vulnerabilities": vulnerabilities,
            "unused_dependencies": unused_dependencies,
            "outdated_dependencies": outdated_dependencies,
            "code_issues": code_issues,
            "summary": {
                "total_vulnerabilities": total_vulns,
                "critical_count": len(vulnerabilities["critical"]),
                "high_count": len(vulnerabilities["high"]),
                "unused_dep_count": len(unused_dependencies),
                "secret_count": len(code_issues["hardcoded_secrets"])
            }
        }
    
    def _run_npm_audit(self, root: Path) -> Dict[str, Any]:
        """Run npm audit for Node.js vulnerabilities."""
        try:
            logger.info("[SECURITY] Running npm audit...")
            
            result = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # npm audit returns non-zero if vulnerabilities found (that's ok)
            data = json.loads(result.stdout)
            
            vulnerabilities = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": []
            }
            
            # Parse npm audit format
            for vuln_id, vuln in data.get("vulnerabilities", {}).items():
                severity = vuln.get("severity", "low").lower()
                
                vuln_info = {
                    "package": vuln_id,
                    "severity": severity,
                    "via": vuln.get("via", []),
                    "range": vuln.get("range", ""),
                    "fix_available": vuln.get("fixAvailable", False)
                }
                
                if severity in vulnerabilities:
                    vulnerabilities[severity].append(vuln_info)
            
            logger.info(f"[SECURITY] npm audit found {sum(len(v) for v in vulnerabilities.values())} vulnerabilities")
            
            return {"success": True, "vulnerabilities": vulnerabilities}
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout"}
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _run_pip_audit(self, root: Path) -> Dict[str, Any]:
        """Run pip-audit for Python vulnerabilities."""
        try:
            logger.info("[SECURITY] Running pip-audit...")
            
            result = subprocess.run(
                ["pip-audit", "--format", "json"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0 and not result.stdout:
                return {"success": False, "error": result.stderr}
            
            data = json.loads(result.stdout)
            
            vulnerabilities = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": []
            }
            
            for vuln in data:
                severity = vuln.get("severity", "UNKNOWN").lower()
                if severity == "unknown":
                    severity = "medium"
                
                vuln_info = {
                    "package": vuln.get("name", ""),
                    "version": vuln.get("version", ""),
                    "cve": vuln.get("id", ""),
                    "fix_version": vuln.get("fix_versions", [])
                }
                
                if severity in vulnerabilities:
                    vulnerabilities[severity].append(vuln_info)
            
            logger.info(f"[SECURITY] pip-audit found {len(data)} vulnerabilities")
            
            return {"success": True, "vulnerabilities": vulnerabilities}
            
        except FileNotFoundError:
            return {"success": False, "error": "pip-audit not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _run_depcheck(self, root: Path) -> Dict[str, Any]:
        """Run depcheck for unused dependencies."""
        try:
            logger.info("[SECURITY] Running depcheck...")
            
            result = subprocess.run(
                ["npx", "-y", "depcheck", "--json"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            data = json.loads(result.stdout)
            
            unused = list(data.get("dependencies", []))
            unused.extend(data.get("devDependencies", []))
            
            logger.info(f"[SECURITY] depcheck found {len(unused)} unused dependencies")
            
            return {"success": True, "unused": unused}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _scan_for_secrets(self, root: Path) -> List[Dict]:
        """Basic secret detection using regex patterns."""
        import re
        
        secret_patterns = [
            (r"api[_-]?key\s*[=:]\s*['\"](.{20,})['\"]", "api_key"),
            (r"secret[_-]?key\s*[=:]\s*['\"](.{20,})['\"]", "secret_key"),
            (r"password\s*[=:]\s*['\"](.{8,})['\"]", "password"),
            (r"sk-[a-zA-Z0-9]{20,}", "openai_key"),
            (r"ghp_[a-zA-Z0-9]{36}", "github_token"),
            (r"AKIA[0-9A-Z]{16}", "aws_access_key"),
        ]
        
        secrets = []
        ignore_dirs = {"node_modules", ".venv", "venv", "__pycache__", "dist", ".git"}
        
        for file_path in root.rglob("*"):
            if any(ignore in str(file_path) for ignore in ignore_dirs):
                continue
            
            if file_path.suffix.lower() in [".py", ".js", ".ts", ".tsx", ".jsx", ".env", ".json", ".yaml", ".yml"]:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    
                    for pattern, secret_type in secret_patterns:
                        for i, line in enumerate(content.split("\n"), 1):
                            if re.search(pattern, line, re.IGNORECASE):
                                secrets.append({
                                    "file": str(file_path.relative_to(root)),
                                    "line": i,
                                    "type": secret_type
                                })
                except Exception:
                    pass
        
        return secrets[:20]  # Limit to 20
    
    def _merge_vulnerabilities(self, target: Dict, source: Dict):
        """Merge vulnerability dicts."""
        for severity in ["critical", "high", "medium", "low"]:
            target[severity].extend(source.get(severity, []))
    
    def save_artifact(self, project_path: str, output_path: Optional[str] = None) -> str:
        """Scan project and save to security_report.json."""
        result = self.scan_project(project_path)
        
        if not output_path:
            output_path = Path(project_path) / ".ships" / "security_report.json"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"[SECURITY] Saved security_report.json to {output_path}")
        
        return str(output_path)
