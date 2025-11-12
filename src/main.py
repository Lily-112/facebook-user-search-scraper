import argparse
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

# Local imports via relative path; this file is executed directly so PYTHONPATH includes src/.
from extractors.facebook_parser import FacebookParser
from extractors.profile_matcher import ProfileMatcher
from outputs.export_manager import ExportManager

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "settings.json")
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

def load_settings(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_inputs(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def ensure_dir(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)

def build_result_record(parsed: Dict[str, Any]) -> Dict[str, Any]:
    # Normalize fields and keep a consistent schema
    return {
        "name": parsed.get("name"),
        "profileImage": parsed.get("profileImage"),
        "coverImage": parsed.get("coverImage"),
        "images": parsed.get("images", []),
        "userId": parsed.get("userId"),
        "profileUrl": parsed.get("profileUrl"),
        "userData": parsed.get("userData", []),
        "_fetchedAt": datetime.utcnow().isoformat() + "Z",
        "_source": parsed.get("_source", "unknown"),
    }

def main():
    parser = argparse.ArgumentParser(description="Facebook User Search Scraper (public profiles only).")
    parser.add_argument(
        "--inputs",
        default=os.path.join(DATA_DIR, "inputs.example.json"),
        help="Path to inputs JSON. Defaults to data/inputs.example.json",
    )
    parser.add_argument(
        "--settings",
        default=CONFIG_PATH,
        help="Path to settings JSON. Defaults to src/config/settings.json",
    )
    parser.add_argument(
        "--output-dir",
        default=DATA_DIR,
        help="Directory to write outputs (json/csv/xml). Defaults to data/",
    )
    parser.add_argument(
        "--formats",
        default="json",
        help="Comma-separated output formats: json,csv,xml. Defaults to json.",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Enable online mode (may attempt to fetch public pages). Default is offline-safe.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    settings = load_settings(args.settings)
    inputs = load_inputs(args.inputs)
    formats = [f.strip().lower() for f in args.formats.split(",") if f.strip()]

    ensure_dir(args.output_dir)

    logging.info("Starting scraper. Mode=%s | Scrolls=%s", "online" if args.online else "offline", settings.get("scrollsAmount"))

    fb_parser = FacebookParser(online=args.online)
    matcher = ProfileMatcher(online=args.online, scrolls_amount=settings.get("scrollsAmount", 1))
    exporter = ExportManager(output_dir=args.output_dir)

    results: List[Dict[str, Any]] = []

    # 1) Direct profile URLs
    for url in inputs.get("profileUrls", []):
        try:
            parsed = fb_parser.parse_profile_from_url(url)
            parsed["_source"] = "profileUrl"
            results.append(build_result_record(parsed))
            logging.info("Parsed profile: %s", parsed.get("name") or url)
        except Exception as e:
            logging.exception("Failed parsing profile URL %s: %s", url, e)

    # 2) Names to search -> best matches
    for name in inputs.get("names", []):
        try:
            candidates = matcher.search_profiles_by_name(name, limit=inputs.get("perNameLimit", 3))
            logging.info("Found %d candidates for '%s'", len(candidates), name)
            for c in candidates:
                try:
                    parsed = fb_parser.parse_profile_from_url(c["profileUrl"])
                    parsed["_source"] = "nameSearch"
                    results.append(build_result_record(parsed))
                except Exception as e:
                    logging.warning("Candidate parse failed for %s: %s", c.get("profileUrl"), e)
        except Exception as e:
            logging.exception("Search failed for name '%s': %s", name, e)

    # 3) Optional embedded HTML documents (offline)
    for html_doc in inputs.get("embeddedHtmlProfiles", []):
        try:
            parsed = fb_parser.parse_profile_html(html_doc.get("html", ""), base_url=html_doc.get("baseUrl"))
            parsed["_source"] = "embeddedHtml"
            results.append(build_result_record(parsed))
            logging.info("Parsed embedded HTML for baseUrl=%s", html_doc.get("baseUrl"))
        except Exception as e:
            logging.exception("Failed parsing embedded HTML: %s", e)

    if not results:
        logging.warning("No results produced. Check inputs or enable --online for live fetches.")

    # Deduplicate by profileUrl or userId
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for r in results:
        key = r.get("profileUrl") or f"id:{r.get('userId')}"
        if key and key not in seen:
            seen.add(key)
            deduped.append(r)

    # Export
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    base_name = f"facebook_users_{ts}"

    if "json" in formats:
        exporter.export_json(deduped, f"{base_name}.json")
    if "csv" in formats:
        exporter.export_csv(deduped, f"{base_name}.csv")
    if "xml" in formats:
        exporter.export_xml(deduped, f"{base_name}.xml", root_tag="users", item_tag="user")

    logging.info("Done. Wrote %d records to %s in formats: %s", len(deduped), args.output_dir, ",".join(formats))

if __name__ == "__main__":
    main()