# main.py
import argparse
from datetime import datetime
from config import BASE_URL, MIN_PUNCH_SCORE
from fetcher import fetch_paginated_posts, fetch_deacon_articles, fetch_ray_articles, fetch_single_url
from cleaner import clean_and_chunk
from scorer import score_chunk
from exporter import export_results


def run_harvest(source="ghost", limit=None, since=None, url=None):
    """
    Run the harvest process and return quotes.

    Args:
        source: Source to fetch from ('ghost', 'deacon', 'ray', 'url')
        limit: Maximum number of articles to process
        since: Only process articles since date (YYYY-MM-DD)
        url: Single URL to fetch (only used when source='url')

    Returns:
        List of unique quote dictionaries
    """
    if source == "url":
        if not url:
            raise ValueError("source='url' requires a URL argument")
        articles = fetch_single_url(url)
    elif source == "ghost":
        print(f"Fetching articles from Ghost pagination: {BASE_URL}")
        articles = fetch_paginated_posts(BASE_URL, since=since, limit=limit)
    elif source == "deacon":
        print(f"Fetching articles from Deacon Harold RSS")
        articles = fetch_deacon_articles(since=since, limit=limit)
    elif source == "ray":
        print(f"Fetching articles from Dr. Ray RSS")
        articles = fetch_ray_articles(since=since, limit=limit)
    else:
        raise ValueError(f"Unknown source: {source}")

    if limit:
        print(f"Limit: {limit} articles")
    if since:
        print(f"Since: {since}")
    print(f"Found {len(articles)} articles to process")

    all_quotes = []

    for i, article in enumerate(articles, 1):
        print(f"Processing article {i}/{len(articles)}: {article['title']}")

        # Clean and chunk the HTML
        chunks = clean_and_chunk(article["raw_html"])
        print(f"  Generated {len(chunks)} chunks")

        # Score each chunk
        for chunk_idx, chunk in enumerate(chunks):
            try:
                result_list = score_chunk(chunk)

                if result_list is None:
                    continue

                if isinstance(result_list, list):
                    for quote in result_list:
                        # Check if quote meets criteria
                        is_quote_worthy = quote.get('is_quote_worthy', False)
                        punch_score = quote.get('punch_score', 0)

                        if is_quote_worthy and punch_score >= MIN_PUNCH_SCORE:
                            # Merge article metadata with score result
                            full_record = {
                                "source_title": article["title"],
                                "source_url": article["url"],
                                "published_at": article["published_at"],
                                **quote
                            }
                            all_quotes.append(full_record)
                            print(f"    Found qualifying quote (score: {punch_score})")

            except Exception as e:
                print(f"    Error scoring chunk {chunk_idx}: {e}")
                continue

    print(f"\nFound {len(all_quotes)} total quotes before deduplication")

    # Deduplicate by edited_line
    seen_lines = set()
    unique_quotes = []

    for quote in all_quotes:
        edited_line = quote.get('edited_line', '')
        if edited_line and edited_line not in seen_lines:
            seen_lines.add(edited_line)
            unique_quotes.append(quote)

    print(f"After deduplication: {len(unique_quotes)} unique quotes")

    return unique_quotes


def main():
    parser = argparse.ArgumentParser(description="Catholic Quote Harvester")
    parser.add_argument('--limit', type=int, help='Limit number of articles to process')
    parser.add_argument('--since', type=str, help='Only process articles since date (YYYY-MM-DD)')
    parser.add_argument('--source', type=str, choices=['ghost', 'deacon', 'ray', 'url'], default='ghost',
                        help='Source to fetch articles from (ghost=Marcus, deacon=Deacon Harold, ray=Dr. Ray, url=single URL)')
    parser.add_argument('--url', type=str, help='Single URL to fetch (required when source=url)')

    args = parser.parse_args()

    # Run the harvest
    unique_quotes = run_harvest(source=args.source, limit=args.limit, since=args.since, url=args.url)

    # Export results
    today = datetime.now().strftime("%Y-%m-%d")
    filename_prefix = f"catholic_quotes_{args.source}_{today}"

    export_results(unique_quotes, filename_prefix=filename_prefix)
    print(f"Exported {len(unique_quotes)} quotes")


if __name__ == "__main__":
    main()