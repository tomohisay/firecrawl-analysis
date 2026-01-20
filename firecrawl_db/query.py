"""Search and filter functionality for Firecrawl data."""

from datetime import datetime
from typing import Optional

from .database import Database
from .models import Scrape


def search_scrapes(
    db: Database,
    query: str,
    limit: int = 100,
) -> list[Scrape]:
    """Full-text search across title, description, and markdown.

    Args:
        db: Database instance
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of matching Scrape objects
    """
    return db.search_fulltext(query, limit)


def filter_scrapes(
    db: Database,
    mode: Optional[str] = None,
    url_contains: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Scrape]:
    """Filter scrapes by various criteria.

    Args:
        db: Database instance
        mode: Filter by scrape mode (e.g., 'scrape', 'crawl')
        url_contains: Filter by URL substring
        date_from: Filter by start date
        date_to: Filter by end date
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of matching Scrape objects
    """
    # Use database's list method with basic filtering
    scrapes = db.list_scrapes(
        limit=limit,
        offset=offset,
        mode=mode,
        url_contains=url_contains,
    )

    # Apply additional date filtering in Python
    if date_from or date_to:
        filtered = []
        for scrape in scrapes:
            if scrape.scraped_at:
                if date_from and scrape.scraped_at < date_from:
                    continue
                if date_to and scrape.scraped_at > date_to:
                    continue
            filtered.append(scrape)
        return filtered

    return scrapes


def get_unique_modes(db: Database) -> list[str]:
    """Get all unique scrape modes in the database."""
    stats = db.get_stats()
    return list(stats.get("by_mode", {}).keys())


def get_url_domains(db: Database, limit: int = 50) -> dict[str, int]:
    """Get count of scrapes by domain.

    Args:
        db: Database instance
        limit: Maximum number of domains to return

    Returns:
        Dictionary mapping domain to count
    """
    from urllib.parse import urlparse

    scrapes = db.list_scrapes(limit=10000)

    domain_counts: dict[str, int] = {}
    for scrape in scrapes:
        try:
            parsed = urlparse(scrape.source_url)
            domain = parsed.netloc
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        except Exception:
            continue

    # Sort by count descending and limit
    sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_domains[:limit])
