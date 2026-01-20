"""Firecrawl API client for direct URL scraping."""

import hashlib
import http.client
import json
import os
import ssl
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Link, Metadata, Scrape


class FirecrawlError(Exception):
    """Firecrawl API error."""

    pass


# Default screenshots directory
SCREENSHOTS_DIR = Path(__file__).parent.parent / "data" / "screenshots"


def _make_request(method: str, endpoint: str, payload: dict = None) -> dict:
    """Send request to Firecrawl API."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise FirecrawlError("FIRECRAWL_API_KEY environment variable is not set")

    conn = http.client.HTTPSConnection("api.firecrawl.dev")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        body = json.dumps(payload) if payload else None
        conn.request(method, endpoint, body, headers)
        res = conn.getresponse()
        data = res.read()
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        raise FirecrawlError(f"API request failed: {e}")
    finally:
        conn.close()


def _download_screenshot(url: str, save_path: Path) -> bool:
    """Download a screenshot from URL and save locally.

    Args:
        url: Screenshot URL to download
        save_path: Local path to save the screenshot

    Returns:
        True if successful, False otherwise
    """
    try:
        parsed = urllib.parse.urlparse(url)

        # Create SSL context that doesn't verify (for signed URLs)
        context = ssl.create_default_context()

        if parsed.scheme == "https":
            conn = http.client.HTTPSConnection(parsed.netloc, context=context)
        else:
            conn = http.client.HTTPConnection(parsed.netloc)

        path_with_query = parsed.path
        if parsed.query:
            path_with_query += "?" + parsed.query

        conn.request("GET", path_with_query)
        response = conn.getresponse()

        if response.status == 200:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(response.read())
            conn.close()
            return True
        else:
            conn.close()
            return False
    except Exception:
        return False


def _generate_screenshot_filename(url: str, device: str) -> str:
    """Generate a unique filename for a screenshot.

    Args:
        url: The source URL
        device: 'desktop' or 'mobile'

    Returns:
        Filename string
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.replace(".", "_").replace(":", "_")
    return f"{timestamp}_{domain}_{url_hash}_{device}.png"


def scrape_url(
    url: str,
    include_html: bool = False,
    include_links: bool = True,
    include_screenshot: bool = True,
    only_main_content: bool = True,
    wait_for: Optional[int] = None,
    screenshots_dir: Optional[Path] = None,
) -> Scrape:
    """Scrape a URL using Firecrawl API with both desktop and mobile screenshots.

    Args:
        url: URL to scrape
        include_html: Include HTML content
        include_links: Include page links
        include_screenshot: Include screenshots (both desktop and mobile)
        only_main_content: Only scrape main content
        wait_for: Wait time in milliseconds for JS rendering
        screenshots_dir: Directory to save screenshots (default: data/screenshots)

    Returns:
        Scrape object with the scraped data

    Raises:
        FirecrawlError: If the API request fails
    """
    if screenshots_dir is None:
        screenshots_dir = SCREENSHOTS_DIR

    # Build formats list for desktop scrape
    formats = ["markdown"]
    if include_html:
        formats.append("html")
    if include_links:
        formats.append("links")
    if include_screenshot:
        formats.append("screenshot@fullPage")

    # First request: Desktop
    desktop_payload = {
        "url": url,
        "formats": formats,
        "onlyMainContent": only_main_content,
        "mobile": False,
    }
    if wait_for:
        desktop_payload["waitFor"] = wait_for

    desktop_result = _make_request("POST", "/v1/scrape", desktop_payload)

    if not desktop_result.get("success", False):
        raise FirecrawlError(desktop_result.get("error", "Unknown error"))

    desktop_data = desktop_result.get("data", {})
    resp_metadata = desktop_data.get("metadata", {})

    # Second request: Mobile (only if screenshot requested)
    mobile_screenshot_url = None
    if include_screenshot:
        mobile_payload = {
            "url": url,
            "formats": ["screenshot@fullPage"],
            "onlyMainContent": only_main_content,
            "mobile": True,
        }
        if wait_for:
            mobile_payload["waitFor"] = wait_for

        try:
            mobile_result = _make_request("POST", "/v1/scrape", mobile_payload)
            if mobile_result.get("success", False):
                mobile_data = mobile_result.get("data", {})
                mobile_screenshot_url = mobile_data.get("screenshot")
        except FirecrawlError:
            pass  # Mobile screenshot failed, continue without it

    # Get screenshot URLs
    desktop_screenshot_url = desktop_data.get("screenshot")

    # Download and save screenshots locally
    desktop_screenshot_path = None
    mobile_screenshot_path = None

    if desktop_screenshot_url:
        filename = _generate_screenshot_filename(url, "desktop")
        save_path = screenshots_dir / filename
        if _download_screenshot(desktop_screenshot_url, save_path):
            desktop_screenshot_path = str(save_path)

    if mobile_screenshot_url:
        filename = _generate_screenshot_filename(url, "mobile")
        save_path = screenshots_dir / filename
        if _download_screenshot(mobile_screenshot_url, save_path):
            mobile_screenshot_path = str(save_path)

    # Create Scrape object
    scrape = Scrape(
        source_url=url,
        mode="scrape",
        scraped_at=datetime.now(),
        source_file=None,
        markdown=desktop_data.get("markdown"),
        html=desktop_data.get("html"),
        screenshot_url=desktop_screenshot_url,  # Keep for backward compatibility
        screenshot_desktop_url=desktop_screenshot_url,
        screenshot_mobile_url=mobile_screenshot_url,
        screenshot_desktop_path=desktop_screenshot_path,
        screenshot_mobile_path=mobile_screenshot_path,
        title=resp_metadata.get("title") or resp_metadata.get("ogTitle"),
        description=resp_metadata.get("description") or resp_metadata.get("ogDescription"),
        language=resp_metadata.get("language"),
        status_code=resp_metadata.get("statusCode"),
    )

    # Extract links
    if desktop_data.get("links"):
        for i, link_url in enumerate(desktop_data["links"]):
            scrape.links.append(Link(url=link_url, position=i))

    # Convert metadata to key-value pairs
    for key, value in resp_metadata.items():
        if value is not None and key not in (
            "title",
            "description",
            "language",
            "statusCode",
            "ogTitle",
            "ogDescription",
        ):
            scrape.metadata.append(
                Metadata(key=key, value=str(value) if not isinstance(value, str) else value)
            )

    return scrape


def download_screenshot_from_url(url: str, save_path: Path) -> bool:
    """Public function to download a screenshot from URL.

    Args:
        url: Screenshot URL to download
        save_path: Local path to save the screenshot

    Returns:
        True if successful, False otherwise
    """
    return _download_screenshot(url, save_path)


def check_api_key() -> bool:
    """Check if Firecrawl API key is configured."""
    return bool(os.environ.get("FIRECRAWL_API_KEY"))
