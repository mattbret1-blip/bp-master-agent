from __future__ import annotations
from datetime import datetime, timedelta, timezone
from .models import ReviewItem

def schedule(item: ReviewItem, quality: int) -> ReviewItem:
    quality = max(0, min(5, int(quality)))
    if quality < 3:
        item.repetitions = 0
        item.interval_days = 1
    elif item.repetitions == 0:
        item.repetitions = 1
        item.interval_days = 1
    elif item.repetitions == 1:
        item.repetitions = 2
        item.interval_days = 3
    else:
        item.repetitions += 1
        item.interval_days = max(1, round(item.interval_days * item.ease))

    if quality >= 4:
        item.ease = min(3.0, item.ease + 0.1)
    elif quality < 3:
        item.ease = max(1.3, item.ease - 0.15)

    item.due_at = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=item.interval_days)).isoformat()
    return item

def due_items(items, limit=10):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    due = []
    for item in items:
        try:
            dt = datetime.fromisoformat(item.due_at.replace("Z","+00:00")).replace(tzinfo=None)
        except ValueError:
            continue
        if dt <= now:
            due.append(item)
    due.sort(key=lambda x: (x.priority != "high", x.due_at))
    return due[:limit]
