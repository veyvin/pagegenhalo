from datetime import datetime
from typing import List, Optional


def log_step(debug_steps: Optional[List[str]], source: str, message: str) -> None:
    """记录调试步骤，便于定位问题。"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"{timestamp} [{source}] {message}"
    if debug_steps is not None:
        debug_steps.append(entry)
    print(entry)

