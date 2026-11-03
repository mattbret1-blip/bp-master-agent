from __future__ import annotations

import os
import sys
from urllib.request import urlopen

url = os.getenv("HEALTHCHECK_URL", "http://127.0.0.1:8000/health")
try:
    with urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"health endpoint returned {response.status}")
except Exception as exc:
    print(f"Health check failed: {exc}", file=sys.stderr)
    raise SystemExit(1)
print("healthy")
