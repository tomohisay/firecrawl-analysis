#!/usr/bin/env python3
"""CLI for Firecrawl JSON to SQLite database."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from tabulate import tabulate

from firecrawl_db import Database
from firecrawl_db.exporter import export_csv, export_json, export_markdown_report
from firecrawl_db.importer import import_json_directory, import_json_file
from firecrawl_db.query import filter_scrapes, get_url_domains, search_scrapes

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "firecrawl.db"


def get_db(db_path: str | None = None) -> Database:
    """Get database instance."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    return Database(path)


def cmd_import(args: argparse.Namespace) -> None:
    """Import JSON files into the database."""
    db = get_db(args.db)
    path = Path(args.path).expanduser()

    if path.is_file():
        success = import_json_file(db, path, skip_duplicates=not args.force)
        if success:
            print("Import completed successfully.")
        else:
            print("Import failed.")
            sys.exit(1)
    elif path.is_dir():
        success, fail = import_json_directory(
            db,
            path,
            recursive=args.recursive,
            skip_duplicates=not args.force,
        )
        print(f"\nImport completed: {success} successful, {fail} failed/skipped")
    else:
        print(f"Path not found: {path}")
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    """List scrapes in the database."""
    db = get_db(args.db)

    scrapes = filter_scrapes(
        db,
        mode=args.mode,
        url_contains=args.url,
        limit=args.limit,
        offset=args.offset,
    )

    if not scrapes:
        print("No scrapes found.")
        return

    table_data = []
    for s in scrapes:
        table_data.append(
            [
                s.id,
                s.title[:50] + "..." if s.title and len(s.title) > 50 else s.title or "",
                s.source_url[:60] + "..." if len(s.source_url) > 60 else s.source_url,
                s.mode,
                s.scraped_at.strftime("%Y-%m-%d %H:%M") if s.scraped_at else "",
            ]
        )

    print(tabulate(table_data, headers=["ID", "Title", "URL", "Mode", "Scraped At"]))
    print(f"\nShowing {len(scrapes)} scrapes")


def cmd_search(args: argparse.Namespace) -> None:
    """Full-text search scrapes."""
    db = get_db(args.db)

    if args.url:
        scrapes = filter_scrapes(db, url_contains=args.url, limit=args.limit)
    else:
        scrapes = search_scrapes(db, args.query, limit=args.limit)

    if not scrapes:
        print("No matching scrapes found.")
        return

    table_data = []
    for s in scrapes:
        table_data.append(
            [
                s.id,
                s.title[:50] + "..." if s.title and len(s.title) > 50 else s.title or "",
                s.source_url[:60] + "..." if len(s.source_url) > 60 else s.source_url,
                s.mode,
            ]
        )

    print(tabulate(table_data, headers=["ID", "Title", "URL", "Mode"]))
    print(f"\nFound {len(scrapes)} matches")


def cmd_show(args: argparse.Namespace) -> None:
    """Show details of a specific scrape."""
    db = get_db(args.db)
    scrape = db.get_scrape(args.id)

    if not scrape:
        print(f"Scrape with ID {args.id} not found.")
        sys.exit(1)

    print(f"ID: {scrape.id}")
    print(f"URL: {scrape.source_url}")
    print(f"Mode: {scrape.mode}")
    print(f"Title: {scrape.title or 'N/A'}")
    print(f"Description: {scrape.description or 'N/A'}")
    print(f"Language: {scrape.language or 'N/A'}")
    print(f"Status Code: {scrape.status_code or 'N/A'}")
    print(f"Scraped At: {scrape.scraped_at or 'N/A'}")
    print(f"Source File: {scrape.source_file or 'N/A'}")
    print(f"Screenshot URL: {scrape.screenshot_url or 'N/A'}")
    print(f"Links: {len(scrape.links)}")
    print(f"Metadata entries: {len(scrape.metadata)}")

    if args.markdown and scrape.markdown:
        print("\n" + "=" * 60)
        print("MARKDOWN CONTENT")
        print("=" * 60)
        print(scrape.markdown)

    if args.links and scrape.links:
        print("\n" + "=" * 60)
        print("LINKS")
        print("=" * 60)
        for link in scrape.links[:50]:  # Limit to 50 links
            print(f"  {link.url}")
        if len(scrape.links) > 50:
            print(f"  ... and {len(scrape.links) - 50} more")

    if args.metadata and scrape.metadata:
        print("\n" + "=" * 60)
        print("METADATA")
        print("=" * 60)
        for meta in scrape.metadata:
            value = meta.value[:100] + "..." if len(meta.value) > 100 else meta.value
            print(f"  {meta.key}: {value}")


def cmd_export(args: argparse.Namespace) -> None:
    """Export scrapes to file."""
    db = get_db(args.db)

    scrapes = filter_scrapes(
        db,
        mode=args.mode,
        url_contains=args.url,
        limit=args.limit,
    )

    if not scrapes:
        print("No scrapes to export.")
        return

    # Load full details for each scrape
    full_scrapes = []
    for s in scrapes:
        full = db.get_scrape(s.id)
        if full:
            full_scrapes.append(full)

    output = args.output

    if args.format == "csv":
        export_csv(full_scrapes, output, include_markdown=args.include_markdown)
    elif args.format == "json":
        export_json(full_scrapes, output, include_markdown=args.include_markdown)
    elif args.format == "markdown":
        export_markdown_report(full_scrapes, output)

    print(f"Exported {len(full_scrapes)} scrapes to {output}")


def cmd_stats(args: argparse.Namespace) -> None:
    """Show database statistics."""
    db = get_db(args.db)
    stats = db.get_stats()

    print("=" * 40)
    print("DATABASE STATISTICS")
    print("=" * 40)
    print(f"Total scrapes: {stats['total_scrapes']}")
    print(f"Total links: {stats['total_links']}")

    if stats.get("by_mode"):
        print("\nBy Mode:")
        for mode, count in stats["by_mode"].items():
            print(f"  {mode}: {count}")

    if stats.get("recent_dates"):
        print("\nRecent Dates:")
        for date, count in stats["recent_dates"].items():
            print(f"  {date}: {count}")

    # Domain statistics
    domains = get_url_domains(db, limit=10)
    if domains:
        print("\nTop Domains:")
        for domain, count in domains.items():
            print(f"  {domain}: {count}")


def cmd_delete(args: argparse.Namespace) -> None:
    """Delete a scrape from the database."""
    db = get_db(args.db)

    if not args.force:
        scrape = db.get_scrape(args.id)
        if not scrape:
            print(f"Scrape with ID {args.id} not found.")
            sys.exit(1)
        print(f"About to delete: {scrape.source_url}")
        confirm = input("Are you sure? [y/N]: ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return

    if db.delete_scrape(args.id):
        print(f"Deleted scrape ID {args.id}")
    else:
        print(f"Scrape with ID {args.id} not found.")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Firecrawl JSON to SQLite CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", help="Database path (default: data/firecrawl.db)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # import command
    import_parser = subparsers.add_parser("import", help="Import JSON files")
    import_parser.add_argument("path", help="JSON file or directory to import")
    import_parser.add_argument("-r", "--recursive", action="store_true", help="Recursive directory search")
    import_parser.add_argument("-f", "--force", action="store_true", help="Re-import duplicates")
    import_parser.set_defaults(func=cmd_import)

    # list command
    list_parser = subparsers.add_parser("list", help="List scrapes")
    list_parser.add_argument("--limit", type=int, default=20, help="Number of results")
    list_parser.add_argument("--offset", type=int, default=0, help="Skip N results")
    list_parser.add_argument("--mode", help="Filter by mode")
    list_parser.add_argument("--url", help="Filter by URL substring")
    list_parser.set_defaults(func=cmd_list)

    # search command
    search_parser = subparsers.add_parser("search", help="Search scrapes")
    search_parser.add_argument("query", nargs="?", help="Search query")
    search_parser.add_argument("--url", help="Search by URL substring")
    search_parser.add_argument("--limit", type=int, default=50, help="Number of results")
    search_parser.set_defaults(func=cmd_search)

    # show command
    show_parser = subparsers.add_parser("show", help="Show scrape details")
    show_parser.add_argument("id", type=int, help="Scrape ID")
    show_parser.add_argument("--markdown", "-m", action="store_true", help="Show markdown content")
    show_parser.add_argument("--links", "-l", action="store_true", help="Show links")
    show_parser.add_argument("--metadata", action="store_true", help="Show metadata")
    show_parser.set_defaults(func=cmd_show)

    # export command
    export_parser = subparsers.add_parser("export", help="Export scrapes")
    export_parser.add_argument("--format", "-f", choices=["csv", "json", "markdown"], default="csv")
    export_parser.add_argument("--output", "-o", required=True, help="Output file")
    export_parser.add_argument("--mode", help="Filter by mode")
    export_parser.add_argument("--url", help="Filter by URL substring")
    export_parser.add_argument("--limit", type=int, default=1000, help="Number of results")
    export_parser.add_argument("--include-markdown", action="store_true", help="Include markdown content")
    export_parser.set_defaults(func=cmd_export)

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a scrape")
    delete_parser.add_argument("id", type=int, help="Scrape ID to delete")
    delete_parser.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    delete_parser.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
