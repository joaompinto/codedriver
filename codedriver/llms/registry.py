"""LLM Registry Management"""

import json
import os
from datetime import datetime, timedelta  # Ensure timedelta is imported
from pathlib import Path
from typing import Dict, Any
from filelock import FileLock
import dateutil.parser  # Add this import

class LLMRegistry:
    def __init__(self, registry_path: str = None):
        if registry_path is None:
            registry_path = str(Path.home() / ".codedriver" / ".llms_registry.json")
        self.registry_path = registry_path
        self.lock_path = f"{registry_path}.lock"
        self.lock = FileLock(self.lock_path)
        self._ensure_registry_exists()

    def _ensure_registry_exists(self):
        """Create registry file if it doesn't exist"""
        try:
            with self.lock:
                if not os.path.exists(self.registry_path):
                    initial_data = {
                        "switches": [],
                        "current_llm": None,
                        "last_updated": None,
                        "rate_limits": {}
                    }
                    with open(self.registry_path, 'w') as f:
                        json.dump(initial_data, f, indent=2)
                else:
                    # Load and migrate existing data
                    with open(self.registry_path, 'r') as f:
                        data = json.load(f)
                    # Migrate if needed
                    data = self._migrate_registry(data)
                    with open(self.registry_path, 'w') as f:
                        json.dump(data, f, indent=2)
        except Exception as e:
            raise Exception(f"Failed to initialize registry: {str(e)}")

    def _migrate_registry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate registry data to latest format"""
        if "rate_limits" not in data:
            data["rate_limits"] = {}
        return data

    def _load_registry(self) -> Dict[str, Any]:
        """Load registry data"""
        try:
            with self.lock:
                with open(self.registry_path, 'r') as f:
                    return json.load(f)
        except FileNotFoundError:
            # Registry was deleted after initialization
            self._ensure_registry_exists()
            return self._load_registry()
        except Exception as e:
            raise Exception(f"Failed to load registry: {str(e)}")

    def _save_registry(self, data: Dict[str, Any]):
        with self.lock:
            with open(self.registry_path, 'w') as f:
                json.dump(data, f, indent=2)

    def record_switch(self, from_llm: str, to_llm: str, reason: str = "overloaded"):
        registry = self._load_registry()
        switch_record = {
            "timestamp": datetime.now().isoformat(),
            "from": from_llm,
            "to": to_llm,
            "reason": reason
        }
        
        registry["switches"].append(switch_record)
        registry["current_llm"] = to_llm
        registry["last_updated"] = datetime.now().isoformat()
        
        self._save_registry(registry)

    def get_current_llm(self) -> str:
        registry = self._load_registry()
        return registry.get("current_llm")

    def get_switch_history(self) -> list:
        registry = self._load_registry()
        return registry.get("switches", [])

    def record_rate_limit(self, llm_name: str, wait_time: int):
        """Record when an LLM will be available again"""
        if wait_time is None:
            raise ValueError("wait_time must not be None")
        
        registry = self._load_registry()
        available_at = (datetime.utcnow() + timedelta(seconds=wait_time)).isoformat()
        
        registry["rate_limits"][llm_name] = {
            "until": available_at,
            "wait_time": wait_time
        }
        self._save_registry(registry)

    def get_rate_limit_info(self, llm_name: str) -> Dict[str, Any]:
        """Get rate limit information for an LLM"""
        registry = self._load_registry()
        rate_limits = registry.get("rate_limits", {})
        if llm_name not in rate_limits:
            return None

        limit_info = rate_limits[llm_name]
        available_at = dateutil.parser.parse(limit_info["until"])
        
        if datetime.utcnow() >= available_at:
            del registry["rate_limits"][llm_name]
            self._save_registry(registry)
            return None
            
        return limit_info