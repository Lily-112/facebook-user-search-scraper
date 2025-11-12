import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from bs4 import BeautifulSoup

OG_IMAGE_KEYS = {"og:image", "og:image:url"}
OG_TITLE_KEYS = {"og:title"}
OG_URL_KEYS = {"og:url", "al:ios:url", "al:android:url"}

class FacebookParser:
    """
    Parses *public* Facebook profile HTML into a normalized record.
    Supports:
      - Parsing from URL (online mode required).
      - Parsing from HTML string (offline-safe; used by tests and demo).
    """

    def __init__(self, online: bool = False, timeout: int = 15):
        self.online = online
        self.timeout = timeout

    def parse_profile_from_url(self, url: str) -> Dict:
        if not self.online:
            # Offline-safe behavior: do not attempt network calls
            logging.info("Offline mode: synthesizing profile for %s", url)
            return self._synthesize_offline(url)

        if requests is None:
            raise RuntimeError("requests not available; cannot fetch in online mode.")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return self.parse_profile_html(resp.text, base_url=url)

    def parse_profile_html(self, html: str, base_url: Optional[str] = None) -> Dict:
        soup = BeautifulSoup(html, "html.parser")

        # Name heuristics: prefer og:title, otherwise title, otherwise fallback from h1
        name = self._first_meta(soup, OG_TITLE_KEYS) or (soup.title.string.strip() if soup.title else None)
        if not name:
            h1 = soup.find("h1")
            name = h1.get_text(strip=True) if h1 else None

        # Profile and cover image heuristics via og:image and common selectors
        profile_image = self._first_meta(soup, OG_IMAGE_KEYS)
        cover_image = None
        # Look for cover image by heuristic class names seen on public profiles
        for selector in ["image.cover", "img.cover", "[data-imgperflogname='profileCoverPhoto'] img", "img[alt*='cover']"]:
            el = soup.select_one(selector)
            if el and el.get("src"):
                cover_image = el["src"]
                break

        # Images gallery: a selection of <img> sources excluding sprites
        images: List[str] = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and not any(ext in src for ext in [".gif", "sprite"]):
                images.append(src)
        images = list(dict.fromkeys(images))[:25]  # unique, limit

        # User ID: try URL patterns, data attributes, and common meta tags
        user_id = self._extract_user_id(base_url) or self._extract_user_id_from_soup(soup)

        profile_url = (
            self._first_meta(soup, OG_URL_KEYS)
            or base_url
        )

        user_data = self._extract_work_education(soup)

        return {
            "name": name,
            "profileImage": profile_image,
            "coverImage": cover_image,
            "images": images,
            "userId": user_id,
            "profileUrl": profile_url,
            "userData": user_data,
        }

    # -------------------- helpers --------------------

    def _first_meta(self, soup: BeautifulSoup, keys: set) -> Optional[str]:
        for k in keys:
            meta = soup.find("meta", property=k) or soup.find("meta", attrs={"name": k})
            if meta and meta.get("content"):
                return meta["content"].strip()
        return None

    def _extract_user_id(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        try:
            parsed = urlparse(url)
            # profile.php?id=4
            qs = parse_qs(parsed.query)
            if "id" in qs and len(qs["id"]) > 0:
                return qs["id"][0]
            # /zuck or /mark.zuckerberg.94 -> cannot guarantee numeric
            # Return last path segment if numeric-like
            last = parsed.path.strip("/").split("/")[-1]
            if last.isdigit():
                return last
        except Exception:
            return None
        return None

    def _extract_user_id_from_soup(self, soup: BeautifulSoup) -> Optional[str]:
        # Look for "entity_id":"<digits>"
        m = re.search(r'"entity_id"\s*:\s*"(\d+)"', soup.text)
        if m:
            return m.group(1)
        # data-gt='{"entity_id":"4"}'
        m = re.search(r'entity_id["\']\s*:\s*["\'](\d+)["\']', soup.text)
        if m:
            return m.group(1)
        return None

    def _extract_work_education(self, soup: BeautifulSoup) -> List[Dict]:
        user_data: List[Dict] = []
        # Simple heuristics: scan list items with known keywords
        for li in soup.find_all(["li", "div", "span"]):
            txt = li.get_text(" ", strip=True)
            if not txt:
                continue
            lowered = txt.lower()
            if any(k in lowered for k in ["works at", "worked at", "founder", "ceo", "studied", "education", "university", "college", "high school"]):
                user_data.append({
                    "type": "work" if any(k in lowered for k in ["works at", "worked at", "founder", "ceo"]) else "education",
                    "text": txt,
                    "icon": None,
                })
            if len(user_data) >= 20:
                break
        return user_data

    def _synthesize_offline(self, url: str) -> Dict:
        """
        Deterministic, offline-safe profile record derived from the URL shape.
        This guarantees the tool is runnable without network while keeping a realistic schema.
        """
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        last = path.split("/")[-1] if path else "profile.php"
        # Fake images derived from a well-formed placeholder service
        base_img = "https://placehold.co/600x400/png"
        name_guess = last.replace(".", " ").replace("-", " ").title() if last and last != "profile.php" else "Facebook User"
        user_id = self._extract_user_id(url) or str(abs(hash(url)) % 10_000_000)

        return {
            "name": name_guess,
            "profileImage": f"{base_img}?text={name_guess}+Profile",
            "coverImage": f"{base_img}?text={name_guess}+Cover",
            "images": [f"{base_img}?text={name_guess}+{i}" for i in range(1, 6)],
            "userId": user_id,
            "profileUrl": url,
            "userData": [
                {"type": "work", "text": f"Works at Example Corp ({name_guess})", "icon": None},
                {"type": "education", "text": "Studied Computer Science at Example University", "icon": None},
            ],
        }