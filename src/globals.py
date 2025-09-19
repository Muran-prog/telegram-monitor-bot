from typing import Dict, Any

# Shared, mutable state to be accessed across modules
# This helps avoid circular import issues.
active_sessions: Dict[int, str] = {}
monitoring_tasks: Dict[tuple, Dict[str, Any]] = {}