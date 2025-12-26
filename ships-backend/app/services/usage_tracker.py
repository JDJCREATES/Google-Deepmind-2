import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

USAGE_DB_FILE = "usage_db.json"

class UsageTracker:
    """
    Tracks usage per IP address or User ID to enforce freemium limits.
    Persists data to a local JSON file to prevent simple restart circumvention.
    """
    def __init__(self):
        self.db_file = USAGE_DB_FILE
        self.usage_data: Dict[str, Any] = self._load_db()

    def _load_db(self) -> Dict[str, Any]:
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_db(self):
        try:
            with open(self.db_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except Exception as e:
            print(f"Error saving usage DB: {e}")

    def can_run_prompt(self, ip_address: str, user_id: Optional[str] = None) -> bool:
        """
        Checks if the user can run a prompt.
        - Authenticated users (user_id present): Unlimited (for now).
        - Anonymous users (ip_address): Max 1 prompt total (or per day, if we want).
        """
        # TEMP: Unlimited for testing
        return True

        if user_id:
            return True  # Logged in users are free for this tier

        # Check IP
        record = self.usage_data.get(ip_address, {"count": 0, "first_seen": None})
        
        # Policy: 1 Prompt Total for Anonymous
        if record["count"] >= 1:
            return False
            
        return True

    def record_usage(self, ip_address: str, user_id: Optional[str] = None):
        """
        Records a prompt execution.
        """
        if user_id:
            return # Don't track logged in users in this simple DB (or track separately)

        now = datetime.now().isoformat()
        if ip_address not in self.usage_data:
            self.usage_data[ip_address] = {"count": 0, "first_seen": now}
        
        self.usage_data[ip_address]["count"] += 1
        self.usage_data[ip_address]["last_seen"] = now
        
        self._save_db()

usage_tracker = UsageTracker()
