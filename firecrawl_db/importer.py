"""JSON import functionality for Firecrawl data."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .database import Database
from .models import Link, Metadata, Scrape


def parse_firecrawl_json(json_path: Path) -> Optional[Scrape]:
    """Parse a Firecrawl JSON file into a Scrape object."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading {json_path}: {e}")
        return None

    # Extract file-level metadata
    file_metadata = data.get("metadata", {})
    source_url = file_metadata.get("url", "")
    mode = file_metadata.get("mode", "scrape")

    scraped_at = None
    timestamp_str = file_metadata.get("timestamp")
    if timestamp_str:
        try:
            scraped_at = datetime.fromisoformat(timestamp_str)
        except ValueError:
            pass

    # Check if response was successful
    response = data.get("response", {})
    if not response.get("success", False):
        print(f"Skipping failed scrape: {json_path}")
        return None

    response_data = response.get("data", {})

    # Extract content
    markdown = response_data.get("markdown")
    html = response_data.get("html")
    screenshot_url = response_data.get("screenshot")

    # Extract metadata from response
    resp_metadata = response_data.get("metadata", {})
    title = resp_metadata.get("title") or resp_metadata.get("ogTitle")
    description = resp_metadata.get("description") or resp_metadata.get("ogDescription")
    language = resp_metadata.get("language")
    status_code = resp_metadata.get("statusCode")

    # Create Scrape object
    scrape = Scrape(
        source_url=source_url,
        mode=mode,
        scraped_at=scraped_at,
        source_file=str(json_path),
        markdown=markdown,
        html=html,
        screenshot_url=screenshot_url,
        title=title,
        description=description,
        language=language,
        status_code=status_code,
    )

    # Extract links from markdown if available
    if markdown:
        links = extract_links_from_markdown(markdown)
        scrape.links = links

    # Extract response links if available (from crawl mode)
    response_links = response_data.get("links", [])
    if response_links:
        for i, url in enumerate(response_links):
            scrape.links.append(Link(url=url, position=i))

    # Convert all metadata to key-value pairs
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


def extract_links_from_markdown(markdown: str) -> list[Link]:
    """Extract links from markdown content."""
    links = []
    # Match markdown links: [text](url)
    pattern = r"\[([^\]]*)\]\(([^)]+)\)"
    matches = re.finditer(pattern, markdown)

    seen_urls = set()
    for i, match in enumerate(matches):
        url = match.group(2)
        # Skip anchors and javascript
        if url.startswith("#") or url.startswith("javascript:"):
            continue
        if url not in seen_urls:
            links.append(Link(url=url, position=i))
            seen_urls.add(url)

    return links


def import_json_file(db: Database, json_path: str | Path, skip_duplicates: bool = True) -> bool:
    """Import a single JSON file into the database.

    Args:
        db: Database instance
        json_path: Path to the JSON file
        skip_duplicates: If True, skip files that have already been imported

    Returns:
        True if import was successful, False otherwise
    """
    json_path = Path(json_path)

    if not json_path.exists():
        print(f"File not found: {json_path}")
        return False

    if not json_path.suffix.lower() == ".json":
        print(f"Not a JSON file: {json_path}")
        return False

    scrape = parse_firecrawl_json(json_path)
    if not scrape:
        return False

    # Check for duplicates
    if skip_duplicates and db.exists_by_url_and_file(scrape.source_url, scrape.source_file):
        print(f"Skipping duplicate: {json_path}")
        return False

    try:
        scrape_id = db.insert_scrape(scrape)
        print(f"Imported: {json_path} (ID: {scrape_id})")
        return True
    except Exception as e:
        print(f"Error importing {json_path}: {e}")
        return False


def import_json_directory(
    db: Database,
    directory: str | Path,
    recursive: bool = False,
    skip_duplicates: bool = True,
) -> tuple[int, int]:
    """Import all JSON files from a directory.

    Args:
        db: Database instance
        directory: Directory path containing JSON files
        recursive: If True, search subdirectories recursively
        skip_duplicates: If True, skip files that have already been imported

    Returns:
        Tuple of (successful imports, failed imports)
    """
    directory = Path(directory)

    if not directory.exists():
        print(f"Directory not found: {directory}")
        return (0, 0)

    if not directory.is_dir():
        print(f"Not a directory: {directory}")
        return (0, 0)

    pattern = "**/*.json" if recursive else "*.json"
    json_files = list(directory.glob(pattern))

    if not json_files:
        print(f"No JSON files found in {directory}")
        return (0, 0)

    print(f"Found {len(json_files)} JSON files")

    success_count = 0
    fail_count = 0

    for json_path in sorted(json_files):
        if import_json_file(db, json_path, skip_duplicates):
            success_count += 1
        else:
            fail_count += 1

    return (success_count, fail_count)
