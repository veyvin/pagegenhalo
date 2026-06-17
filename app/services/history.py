# 生成历史：内存存储最近 N 条，供预览与重新发布

import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

# 最多保留条数
MAX_HISTORY = 50

_history: deque = deque(maxlen=MAX_HISTORY)


def add_record(
    title: str,
    content: str,
    status: str = "draft",
) -> str:
    """追加一条记录，返回 id。status: draft | published | preview"""
    record_id = str(uuid.uuid4())[:8]
    _history.appendleft(
        {
            "id": record_id,
            "title": title,
            "content": content,
            "created_at": datetime.now().isoformat(),
            "status": status,
        }
    )
    return record_id


def get_list(limit: int = 20) -> List[Dict[str, Any]]:
    """返回最近 limit 条记录（不含 content 以减小体积）。"""
    items = []
    for i, r in enumerate(_history):
        if i >= limit:
            break
        items.append(
            {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "status": r["status"],
            }
        )
    return items


def get_one(record_id: str) -> Optional[Dict[str, Any]]:
    """根据 id 取一条完整记录（含 content）。"""
    for r in _history:
        if r["id"] == record_id:
            return dict(r)
    return None
