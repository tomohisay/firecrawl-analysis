"""Export functionality for Firecrawl data."""

import csv
import json
from pathlib import Path
from typing import TextIO

from .models import Scrape


def export_csv(
    scrapes: list[Scrape],
    output: str | Path | TextIO,
    include_markdown: bool = False,
) -> None:
    """Export scrapes to CSV format.

    Args:
        scrapes: List of Scrape objects to export
        output: File path or file-like object
        include_markdown: Include full markdown content (can be large)
    """
    fieldnames = [
        "id",
        "source_url",
        "mode",
        "title",
        "description",
        "language",
        "status_code",
        "scraped_at",
        "link_count",
    ]
    if include_markdown:
        fieldnames.append("markdown")

    def write_csv(f: TextIO) -> None:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for scrape in scrapes:
            row = {
                "id": scrape.id,
                "source_url": scrape.source_url,
                "mode": scrape.mode,
                "title": scrape.title,
                "description": scrape.description,
                "language": scrape.language,
                "status_code": scrape.status_code,
                "scraped_at": scrape.scraped_at.isoformat() if scrape.scraped_at else "",
                "link_count": len(scrape.links),
            }
            if include_markdown:
                row["markdown"] = scrape.markdown or ""
            writer.writerow(row)

    if isinstance(output, (str, Path)):
        with open(output, "w", newline="", encoding="utf-8") as f:
            write_csv(f)
    else:
        write_csv(output)


def export_json(
    scrapes: list[Scrape],
    output: str | Path | TextIO,
    include_markdown: bool = True,
    include_html: bool = False,
    pretty: bool = True,
) -> None:
    """Export scrapes to JSON format.

    Args:
        scrapes: List of Scrape objects to export
        output: File path or file-like object
        include_markdown: Include markdown content
        include_html: Include HTML content (can be very large)
        pretty: Pretty-print JSON with indentation
    """
    data = []
    for scrape in scrapes:
        item = scrape.to_dict()
        if not include_markdown:
            item.pop("markdown", None)
        if not include_html:
            item.pop("html", None)
        data.append(item)

    indent = 2 if pretty else None
    json_str = json.dumps(data, ensure_ascii=False, indent=indent)

    if isinstance(output, (str, Path)):
        with open(output, "w", encoding="utf-8") as f:
            f.write(json_str)
    else:
        output.write(json_str)


def export_markdown_report(
    scrapes: list[Scrape],
    output: str | Path | TextIO,
) -> None:
    """Export scrapes as a markdown report.

    Args:
        scrapes: List of Scrape objects to export
        output: File path or file-like object
    """
    lines = ["# Firecrawl Scrape Report\n"]
    lines.append(f"Total scrapes: {len(scrapes)}\n")
    lines.append("---\n")

    for i, scrape in enumerate(scrapes, 1):
        lines.append(f"## {i}. {scrape.title or 'Untitled'}\n")
        lines.append(f"**URL:** {scrape.source_url}\n")
        lines.append(f"**Mode:** {scrape.mode}\n")
        if scrape.scraped_at:
            lines.append(f"**Scraped:** {scrape.scraped_at.isoformat()}\n")
        if scrape.description:
            lines.append(f"\n> {scrape.description}\n")
        lines.append("\n---\n")

    content = "\n".join(lines)

    if isinstance(output, (str, Path)):
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        output.write(content)
