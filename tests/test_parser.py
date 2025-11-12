import os
import sys

# Ensure src/ is importable when running pytest from repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from extractors.facebook_parser import FacebookParser  # noqa: E402

def test_parse_profile_html_minimal():
    html = """
    <html>
      <head>
        <title>Jane Doe - Facebook</title>
        <meta property="og:title" content="Jane Doe"/>
        <meta property="og:image" content="https://example.com/jane_profile.jpg"/>
        <meta property="og:url" content="https://www.facebook.com/profile.php?id=12345"/>
      </head>
      <body>
        <h1>Jane Doe</h1>
        <ul>
          <li>Works at Example Corp</li>
          <li>Studied Computer Science at Example University</li>
        </ul>
        <img src="https://example.com/jane1.jpg"/>
        <img src="https://example.com/jane2.jpg"/>
      </body>
    </html>
    """
    parser = FacebookParser(online=False)
    rec = parser.parse_profile_html(html, base_url="https://www.facebook.com/profile.php?id=12345")
    assert rec["name"] == "Jane Doe"
    assert rec["userId"] == "12345"
    assert rec["profileUrl"] == "https://www.facebook.com/profile.php?id=12345"
    assert "https://example.com/jane_profile.jpg" == rec["profileImage"]
    assert len(rec["images"]) >= 2
    # userData should classify work and education
    types = {d["type"] for d in rec["userData"]}
    assert "work" in types or "education" in types

def test_parse_profile_from_url_offline_synth():
    parser = FacebookParser(online=False)
    url = "https://www.facebook.com/ada.lovelace"
    rec = parser.parse_profile_from_url(url)
    assert rec["name"].lower().startswith("ada")
    assert rec["profileUrl"] == url
    assert rec["userId"] is not None
    assert isinstance(rec["images"], list) and len(rec["images"]) >= 3