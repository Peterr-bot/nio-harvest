# exporter.py
import json
import csv
import os


def export_results(quotes: list[dict], output_dir: str = "data/processed", filename_prefix: str = "marcus_quotes"):
    """Export quotes to JSON and CSV files."""
    if not quotes:
        print("No quotes to export.")
        return

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Export JSON
    json_path = os.path.join(output_dir, f"{filename_prefix}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(quotes, f, indent=2, ensure_ascii=False)

    print(f"JSON exported to: {json_path}")

    # Export CSV
    csv_path = os.path.join(output_dir, f"{filename_prefix}.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'source_title',
            'source_url',
            'published_at',
            'quote_text',
            'category',
            'punch_score',
            'tone',
            'tweet_version',
            'card_version',
            'caption_version'
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for quote in quotes:
            row = {
                'source_title': quote.get('source_title', ''),
                'source_url': quote.get('source_url', ''),
                'published_at': quote.get('published_at', ''),
                'quote_text': quote.get('edited_line', ''),
                'category': quote.get('category', ''),
                'punch_score': quote.get('punch_score', ''),
                'tone': quote.get('tone', ''),
                'tweet_version': quote.get('tweet_version', ''),
                'card_version': quote.get('card_version', ''),
                'caption_version': quote.get('caption_version', '')
            }
            writer.writerow(row)

    print(f"CSV exported to: {csv_path}")