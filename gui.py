#!/usr/bin/env python3
"""Streamlit GUI for Firecrawl JSON to SQLite database."""

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from firecrawl_db import Database
from firecrawl_db.exporter import export_csv, export_json
from firecrawl_db.importer import import_json_directory, import_json_file
from firecrawl_db.query import filter_scrapes, get_unique_modes, get_url_domains, search_scrapes
from firecrawl_db.scraper import FirecrawlError, check_api_key, scrape_url

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "firecrawl.db"


@st.cache_resource
def get_db() -> Database:
    """Get cached database instance."""
    return Database(DEFAULT_DB_PATH)


def main() -> None:
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Firecrawl Data Viewer",
        page_icon="🔥",
        layout="wide",
    )

    st.title("🔥 Firecrawl Data Viewer")

    db = get_db()

    # Sidebar
    with st.sidebar:
        st.header("Search & Filter")

        # Full-text search
        search_query = st.text_input("Full-text Search", placeholder="Enter keywords...")

        # URL filter
        url_filter = st.text_input("URL Contains", placeholder="example.com")

        # Mode filter
        modes = ["All"] + get_unique_modes(db)
        selected_mode = st.selectbox("Mode", modes)
        mode_filter = None if selected_mode == "All" else selected_mode

        # Limit
        limit = st.slider("Max Results", 10, 500, 100)

        st.divider()

        # Import section
        st.header("Import Data")
        import_path = st.text_input("Path to import", placeholder="~/FirecrawlAPI/")
        col1, col2 = st.columns(2)
        with col1:
            recursive = st.checkbox("Recursive")
        with col2:
            force = st.checkbox("Force")

        if st.button("Import", type="primary"):
            if import_path:
                path = Path(import_path).expanduser()
                with st.spinner("Importing..."):
                    if path.is_file():
                        success = import_json_file(db, path, skip_duplicates=not force)
                        if success:
                            st.success("Import successful!")
                        else:
                            st.warning("Import failed or skipped.")
                    elif path.is_dir():
                        success, fail = import_json_directory(
                            db, path, recursive=recursive, skip_duplicates=not force
                        )
                        st.success(f"Imported: {success} success, {fail} failed/skipped")
                        st.cache_resource.clear()
                    else:
                        st.error("Path not found")
            else:
                st.warning("Please enter a path")

        st.divider()

        # Fetch URL section
        st.header("Fetch URL")
        if not check_api_key():
            st.warning("FIRECRAWL_API_KEY not set")
        else:
            fetch_urls = st.text_area(
                "URLs to fetch (1 per line)",
                placeholder="https://example.com\nhttps://example.org",
                height=100,
            )
            col1, col2 = st.columns(2)
            with col1:
                include_html = st.checkbox("Include HTML")
            with col2:
                include_screenshot = st.checkbox("Screenshot (PC+Mobile)", value=True)

            if st.button("Fetch & Save", type="primary"):
                # Parse URLs (one per line)
                urls = [u.strip() for u in fetch_urls.strip().split("\n") if u.strip()]

                if urls:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results = {"success": 0, "failed": 0, "ids": []}

                    for i, url in enumerate(urls):
                        status_text.text(f"Fetching {i+1}/{len(urls)}: {url[:50]}...")
                        try:
                            scrape = scrape_url(
                                url,
                                include_html=include_html,
                                include_links=True,
                                include_screenshot=include_screenshot,
                            )
                            scrape_id = db.insert_scrape(scrape)
                            results["success"] += 1
                            results["ids"].append(scrape_id)
                        except FirecrawlError as e:
                            results["failed"] += 1
                            st.warning(f"Failed: {url} - {e}")

                        progress_bar.progress((i + 1) / len(urls))

                    status_text.empty()
                    progress_bar.empty()

                    if results["success"] > 0:
                        st.success(
                            f"Completed! {results['success']} success, {results['failed']} failed\n"
                            f"IDs: {results['ids']}"
                        )
                        st.cache_resource.clear()
                        st.rerun()
                    else:
                        st.error("All URLs failed")
                else:
                    st.warning("Please enter at least one URL")

        st.divider()

        # Statistics
        st.header("Statistics")
        stats = db.get_stats()
        st.metric("Total Scrapes", stats["total_scrapes"])
        st.metric("Total Links", stats["total_links"])

        if stats.get("by_mode"):
            st.write("**By Mode:**")
            for mode, count in stats["by_mode"].items():
                st.write(f"- {mode}: {count}")

    # Main content
    # Fetch scrapes
    if search_query:
        scrapes = search_scrapes(db, search_query, limit=limit)
    else:
        scrapes = filter_scrapes(
            db,
            mode=mode_filter,
            url_contains=url_filter if url_filter else None,
            limit=limit,
        )

    # Display results
    if not scrapes:
        st.info("No scrapes found. Try adjusting your search criteria or import some data.")
        return

    st.subheader(f"Results ({len(scrapes)} scrapes)")

    # Create DataFrame for display
    df_data = []
    for s in scrapes:
        df_data.append(
            {
                "ID": s.id,
                "Title": s.title or "",
                "URL": s.source_url,
                "Mode": s.mode,
                "Language": s.language or "",
                "Status": s.status_code,
                "Scraped At": s.scraped_at.strftime("%Y-%m-%d %H:%M") if s.scraped_at else "",
            }
        )

    df = pd.DataFrame(df_data)

    # Display table with selection
    selected_id = None
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.TextColumn("URL", width="large"),
            "Title": st.column_config.TextColumn("Title", width="medium"),
        },
    )

    # Export buttons
    col1, col2, col3 = st.columns(3)

    # Load full scrapes for export
    full_scrapes = [db.get_scrape(s.id) for s in scrapes]
    full_scrapes = [s for s in full_scrapes if s]

    with col1:
        csv_buffer = io.StringIO()
        export_csv(full_scrapes, csv_buffer, include_markdown=False)
        st.download_button(
            "Download CSV",
            csv_buffer.getvalue(),
            file_name="firecrawl_export.csv",
            mime="text/csv",
        )

    with col2:
        json_buffer = io.StringIO()
        export_json(full_scrapes, json_buffer, include_markdown=True)
        st.download_button(
            "Download JSON",
            json_buffer.getvalue(),
            file_name="firecrawl_export.json",
            mime="application/json",
        )

    with col3:
        json_buffer_no_md = io.StringIO()
        export_json(full_scrapes, json_buffer_no_md, include_markdown=False)
        st.download_button(
            "JSON (no markdown)",
            json_buffer_no_md.getvalue(),
            file_name="firecrawl_export_light.json",
            mime="application/json",
        )

    st.divider()

    # Detail view
    st.subheader("Detail View")

    # Scrape selector
    scrape_options = {f"{s.id}: {s.title or s.source_url[:50]}": s.id for s in scrapes}
    selected_key = st.selectbox("Select a scrape to view details", list(scrape_options.keys()))

    if selected_key:
        selected_id = scrape_options[selected_key]
        scrape = db.get_scrape(selected_id)

        if scrape:
            # Info columns
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**URL:** [{scrape.source_url}]({scrape.source_url})")
                st.write(f"**Mode:** {scrape.mode}")
                st.write(f"**Language:** {scrape.language or 'N/A'}")
            with col2:
                st.write(f"**Title:** {scrape.title or 'N/A'}")
                st.write(f"**Status Code:** {scrape.status_code or 'N/A'}")
                st.write(f"**Links:** {len(scrape.links)}")
            with col3:
                st.write(f"**Scraped At:** {scrape.scraped_at or 'N/A'}")
                st.write(f"**Source File:** {scrape.source_file or 'N/A'}")

            if scrape.description:
                st.write(f"**Description:** {scrape.description}")

            # Tabs for content
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["Markdown", "HTML", "Screenshot", "Links", "Metadata"])

            with tab1:
                if scrape.markdown:
                    with st.expander("View Markdown Source", expanded=False):
                        st.code(scrape.markdown, language="markdown")
                    st.divider()
                    st.markdown("**Rendered Preview:**")
                    st.markdown(scrape.markdown)
                else:
                    st.info("No markdown content available")

            with tab2:
                if scrape.html:
                    st.code(scrape.html[:10000], language="html")
                    if len(scrape.html) > 10000:
                        st.warning(f"HTML truncated (total: {len(scrape.html)} chars)")
                else:
                    st.info("No HTML content available")

            with tab3:
                has_screenshot = (
                    scrape.screenshot_desktop_path
                    or scrape.screenshot_mobile_path
                    or scrape.screenshot_desktop_url
                    or scrape.screenshot_mobile_url
                    or scrape.screenshot_url
                )

                if has_screenshot:
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**Desktop**")
                        if scrape.screenshot_desktop_path:
                            st.write(f"Local: `{scrape.screenshot_desktop_path}`")
                            try:
                                st.image(scrape.screenshot_desktop_path, use_container_width=True)
                            except Exception:
                                st.warning("Failed to load local image")
                        elif scrape.screenshot_desktop_url or scrape.screenshot_url:
                            url = scrape.screenshot_desktop_url or scrape.screenshot_url
                            with st.expander("URL"):
                                st.code(url)
                            try:
                                st.image(url, use_container_width=True)
                            except Exception:
                                st.warning("Failed to load image from URL")
                        else:
                            st.info("No desktop screenshot")

                    with col2:
                        st.write("**Mobile**")
                        if scrape.screenshot_mobile_path:
                            st.write(f"Local: `{scrape.screenshot_mobile_path}`")
                            try:
                                st.image(scrape.screenshot_mobile_path, use_container_width=True)
                            except Exception:
                                st.warning("Failed to load local image")
                        elif scrape.screenshot_mobile_url:
                            with st.expander("URL"):
                                st.code(scrape.screenshot_mobile_url)
                            try:
                                st.image(scrape.screenshot_mobile_url, use_container_width=True)
                            except Exception:
                                st.warning("Failed to load image from URL")
                        else:
                            st.info("No mobile screenshot")
                else:
                    st.info("No screenshot available")

            with tab4:
                if scrape.links:
                    links_df = pd.DataFrame(
                        [{"Position": l.position, "URL": l.url} for l in scrape.links]
                    )
                    st.dataframe(links_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No links found")

            with tab5:
                if scrape.metadata:
                    meta_df = pd.DataFrame(
                        [{"Key": m.key, "Value": m.value[:200]} for m in scrape.metadata]
                    )
                    st.dataframe(meta_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No metadata available")

            # Delete button
            st.divider()
            if st.button("Delete this scrape", type="secondary"):
                if db.delete_scrape(selected_id):
                    st.success(f"Deleted scrape ID {selected_id}")
                    st.cache_resource.clear()
                    st.rerun()
                else:
                    st.error("Failed to delete")


if __name__ == "__main__":
    main()
