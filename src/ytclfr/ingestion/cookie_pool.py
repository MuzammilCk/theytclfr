import random
from pathlib import Path

from ytclfr.core.config import Settings
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)

class CookiePool:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cookies_dir = Path(settings.ytdlp_cookies_dir) if settings.ytdlp_cookies_dir else None
        self._exhausted: set[Path] = set()

    def get_cookie(self) -> Path | None:
        if not self.cookies_dir or not self.cookies_dir.exists():
            # Fall back to single file
            single_file = Path(self.settings.ytdlp_cookies_file) if self.settings.ytdlp_cookies_file else None
            return single_file

        cookies = list(self.cookies_dir.glob("*.txt"))
        
        # Minimum of 5 cookies required for pool (technical debt stopgap)
        if len(cookies) < 5:
            logger.warning("Cookie pool has less than 5 cookies! This is a severe risk of IP ban.")

        active_cookies = [c for c in cookies if c not in self._exhausted]
        if not active_cookies:
            # If all are exhausted, we might as well reset or just fail.
            # We'll reset for now.
            logger.warning("All cookies exhausted. Resetting cookie pool.")
            self._exhausted.clear()
            active_cookies = cookies

        if not active_cookies:
            return None

        # Randomly rotate
        return random.choice(active_cookies)

    def mark_exhausted(self, cookie_file: Path) -> None:
        logger.warning(f"Marking cookie {cookie_file} as exhausted.")
        self._exhausted.add(cookie_file)
