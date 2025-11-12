import logging
import re
from typing import Dict, List

from .utils_scroll import ScrollPaginator

class ProfileMatcher:
    """
    Turns a human name into candidate public profile URLs.
    In offline mode, this generates deterministic, realistic Facebook URLs.
    In online mode, this module *can* be extended to call a public search engine
    and parse links, but that is intentionally avoided here to keep the tool runnable.
    """

    def __init__(self, online: bool = False, scrolls_amount: int = 1):
        self.online = online
        self.scrolls_amount = max(1, int(scrolls_amount))

    def search_profiles_by_name(self, name: str, limit: int = 3) -> List[Dict]:
        name = name.strip()
        if not name:
            return []
        logging.info("ProfileMatcher searching for: %s (limit=%d)", name, limit)

        if not self.online:
            # Offline deterministic candidates
            slug = self._slugify(name)
            candidates = [
                {"name": name, "profileUrl": f"https://www.facebook.com/{slug}"},
                {"name": name, "profileUrl": f"https://www.facebook.com/{slug}.official"},
                {"name": name, "profileUrl": f"https://www.facebook.com/profile.php?id={self._stable_id(name)}"},
            ]
            return candidates[:limit]

        # Online mode stub with paginator (extendable)
        paginator = ScrollPaginator(fetch=lambda page: self._online_fetch_stub(name, page))
        pages = paginator.collect_pages(self.scrolls_amount)
        dedup = {}
        for page in pages:
            for url in page:
                dedup[url] = {"name": name, "profileUrl": url}
                if len(dedup) >= limit:
                    break
            if len(dedup) >= limit:
                break
        return list(dedup.values())

    # -------------------- helpers --------------------

    def _slugify(self, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", ".", name.strip().lower())
        slug = re.sub(r"\.+", ".", slug).strip(".")
        return slug or "user"

    def _stable_id(self, name: str) -> int:
        return abs(hash(f"fb::{name}")) % 100_000_000

    def _online_fetch_stub(self, name: str, page: int) -> List[str]:
        # This stub intentionally avoids network usage. It produces plausible variations per page.
        base = self._slugify(name)
        return [
            f"https://www.facebook.com/{base}",
            f"https://www.facebook.com/{base}.{page}",
            f"https://www.facebook.com/profile.php?id={self._stable_id(name) + page}",
        ]