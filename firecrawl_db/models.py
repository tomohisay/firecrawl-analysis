"""Dataclass models for Firecrawl data."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Link:
    """Represents a link found in a scraped page."""

    url: str
    position: int
    id: Optional[int] = None
    scrape_id: Optional[int] = None


@dataclass
class Metadata:
    """Represents a key-value metadata entry for a scrape."""

    key: str
    value: str
    id: Optional[int] = None
    scrape_id: Optional[int] = None


@dataclass
class Scrape:
    """Represents a scraped page from Firecrawl."""

    source_url: str
    mode: str
    scraped_at: Optional[datetime] = None
    source_file: Optional[str] = None
    markdown: Optional[str] = None
    html: Optional[str] = None
    screenshot_url: Optional[str] = None
    screenshot_desktop_url: Optional[str] = None
    screenshot_mobile_url: Optional[str] = None
    screenshot_desktop_path: Optional[str] = None
    screenshot_mobile_path: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    status_code: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    id: Optional[int] = None
    links: list[Link] = field(default_factory=list)
    metadata: list[Metadata] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "source_url": self.source_url,
            "mode": self.mode,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "source_file": self.source_file,
            "markdown": self.markdown,
            "html": self.html,
            "screenshot_url": self.screenshot_url,
            "screenshot_desktop_url": self.screenshot_desktop_url,
            "screenshot_mobile_url": self.screenshot_mobile_url,
            "screenshot_desktop_path": self.screenshot_desktop_path,
            "screenshot_mobile_path": self.screenshot_mobile_path,
            "title": self.title,
            "description": self.description,
            "language": self.language,
            "status_code": self.status_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "links": [{"url": link.url, "position": link.position} for link in self.links],
            "metadata": {m.key: m.value for m in self.metadata},
        }
