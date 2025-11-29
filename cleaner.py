# cleaner.py
from bs4 import BeautifulSoup


def clean_and_chunk(html_content: str, min_length: int = 50, max_chunk_len: int = 1000) -> list[str]:
    """Clean HTML content and split into chunks."""
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove junk tags
    junk_tags = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript']
    for tag in junk_tags:
        for element in soup.find_all(tag):
            element.decompose()

    # Get clean text
    text = soup.get_text(separator="\n\n")

    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Filter paragraphs by minimum length
    valid_paragraphs = [p for p in paragraphs if len(p) >= min_length]

    if not valid_paragraphs:
        return []

    # Build chunks
    chunks = []
    current_chunk = ""

    for paragraph in valid_paragraphs:
        # If adding this paragraph would exceed max_chunk_len
        if current_chunk and len(current_chunk) + len(paragraph) + 2 > max_chunk_len:
            # Save current chunk and start new one
            chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks