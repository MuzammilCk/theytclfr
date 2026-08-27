"""Rate limiting with proxy-aware IP detection.

Phase 10: In distributed cloud deployments behind a load balancer,
the direct remote address is the load balancer's IP, not the client's.
This module extracts the real client IP from X-Forwarded-For headers
to prevent rate-limiting the entire load balancer as a single client.
"""

from fastapi import Request
from slowapi import Limiter


def get_real_ip(request: Request) -> str:
    """Extract the real client IP from proxy headers.

    Reads the first IP in X-Forwarded-For (set by the load balancer).
    Falls back to the direct remote address for non-proxied requests.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=get_real_ip)
