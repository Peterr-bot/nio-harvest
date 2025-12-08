# fetcher.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import parsedate_to_datetime
from config import HEADERS, SUBSTACK_RSS_URL, DEACON_RSS_URL, RAY_RSS_URL

# Robust headers for Streamlit Cloud deployment
# Note: requests library handles gzip automatically, so we don't need to specify Accept-Encoding
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def get_article_links(base_url: str) -> list[str]:
    """Get all article links from the base URL."""
    try:
        # Try browser headers first, fallback to basic headers
        try:
            response = requests.get(base_url, headers=BROWSER_HEADERS, timeout=10)
            response.raise_for_status()
        except:
            response = requests.get(base_url, headers=HEADERS, timeout=10)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        links = []

        # Look for article links - Ghost typically uses these patterns
        article_links = soup.find_all('a', href=True)

        for link in article_links:
            href = link.get('href')
            if href and ('/t/' in href or '/posts/' in href or '/p/' in href):
                if href.startswith('/'):
                    full_url = f"https://www.marcusbpeter.com{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue

                if full_url not in links and 'marcusbpeter.com' in full_url:
                    links.append(full_url)

        return links

    except requests.RequestException as e:
        print(f"Error fetching article links: {e}")
        return []


def fetch_article(url: str) -> dict:
    """Fetch a single article and extract metadata."""
    try:
        # Try browser headers first, fallback to basic headers
        try:
            response = requests.get(url, headers=BROWSER_HEADERS, timeout=10)
            response.raise_for_status()
        except:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()

        # Ensure proper encoding - requests should handle this automatically
        response.encoding = response.apparent_encoding
        html = response.text or ""
        print(f"[fetch_article] {url} -> html length: {len(html)}")

        soup = BeautifulSoup(html, 'html.parser')

        # ---- TITLE ----
        title_elem = (
            soup.find('meta', property='og:title')
            or soup.find('meta', attrs={'name': 'twitter:title'})
            or soup.find('title')
            or soup.find('h1')
        )
        title = title_elem.get("content").strip() if title_elem and title_elem.has_attr("content") else (
            title_elem.get_text().strip() if title_elem else "Untitled"
        )

        # ---- PUBLISHED DATE ----
        published_at = datetime.now().strftime("%Y-%m-%d")
        date_selectors = [
            'time[datetime]',
            '.post-date',
            '.published',
            '[class*="date"]',
        ]

        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if not date_elem:
                continue

            date_text = (date_elem.get('datetime') or date_elem.get_text() or "").strip()
            if not date_text:
                continue

            date_formats = [
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S%z",
                "%B %d, %Y",
            ]

            parsed = None
            for fmt in date_formats:
                try:
                    parsed = datetime.strptime(date_text.split('T')[0], fmt)
                    break
                except ValueError:
                    continue

            if parsed:
                published_at = parsed.strftime("%Y-%m-%d")
                break

        # ---- CONTENT ----
        # Add Ghost-friendly selectors first
        content_selectors = [
            '.gh-content',
            '.gh-article',
            '.post-full-content',
            '.post-content',
            '.content',
            'article',
            'main',
            '.entry-content',
        ]

        raw_html = ""
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                raw_html = str(content_elem)
                break

        if not raw_html:
            # Fallback: body
            body = soup.find('body')
            if body:
                raw_html = str(body)
            else:
                # Final fallback: entire HTML so we never return empty
                raw_html = html

        return {
            "title": title,
            "url": url,
            "published_at": published_at,
            "raw_html": raw_html,
        }

    except requests.RequestException as e:
        print(f"Error fetching article {url}: {e}")
        return {
            "title": "Error",
            "url": url,
            "published_at": datetime.now().strftime("%Y-%m-%d"),
            "raw_html": "",
        }


def fetch_articles(base_url: str, limit: int | None = None, since: str | None = None) -> list[dict]:
    """Fetch multiple articles with optional filtering."""
    article_urls = get_article_links(base_url)

    if limit:
        article_urls = article_urls[:limit]

    articles = []
    for url in article_urls:
        article = fetch_article(url)

        # Filter by date if since is provided
        if since:
            try:
                article_date = datetime.strptime(article["published_at"], "%Y-%m-%d")
                since_date = datetime.strptime(since, "%Y-%m-%d")
                if article_date < since_date:
                    continue
            except ValueError:
                # If date parsing fails, include the article
                pass

        articles.append(article)
        print(f"Fetched: {article['title']}")

    return articles


def fetch_substack_articles(rss_url: str, since: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Fetch articles from a Substack RSS feed.

    Returns a list of dicts with:
    - title: str
    - url: str
    - published_at: "YYYY-MM-DD"
    - raw_html: str   # use <content:encoded> if present, else <description>
    """
    try:
        response = requests.get(rss_url, headers=HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, features="xml")
        items = soup.find_all('item')

        articles = []
        for item in items:
            # Extract title
            title_elem = item.find('title')
            title = title_elem.get_text().strip() if title_elem else "Untitled"

            # Extract URL
            link_elem = item.find('link')
            url = link_elem.get_text().strip() if link_elem else ""

            # Extract published date
            pub_date_elem = item.find('pubDate')
            published_at = datetime.now().strftime("%Y-%m-%d")

            if pub_date_elem:
                try:
                    # Parse RFC 2822 format used in RSS
                    pub_date_str = pub_date_elem.get_text().strip()
                    parsed_date = parsedate_to_datetime(pub_date_str)
                    # Convert to naive datetime for consistency
                    if parsed_date.tzinfo:
                        parsed_date = parsed_date.replace(tzinfo=None)
                    published_at = parsed_date.strftime("%Y-%m-%d")
                except Exception:
                    # Fallback to current date if parsing fails
                    pass

            # Filter by date if since is provided
            if since:
                try:
                    article_date = datetime.strptime(published_at, "%Y-%m-%d")
                    since_date = datetime.strptime(since, "%Y-%m-%d")
                    if article_date < since_date:
                        continue
                except ValueError:
                    # If date parsing fails, include the article
                    pass

            # Extract content - prefer content:encoded over description
            content_elem = item.find('content:encoded') or item.find('description')
            raw_html = ""
            if content_elem:
                raw_html = content_elem.get_text() if content_elem.string else str(content_elem)

            article = {
                "title": title,
                "url": url,
                "published_at": published_at,
                "raw_html": raw_html
            }

            articles.append(article)
            print(f"Fetched from RSS: {title}")

            # Apply limit if specified
            if limit and len(articles) >= limit:
                break

        return articles

    except requests.RequestException as e:
        print(f"Error fetching RSS feed: {e}")
        return []
    except Exception as e:
        print(f"Error parsing RSS feed: {e}")
        return []


def fetch_archive_articles(archive_url: str, since: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Crawl an archive page that lists many posts and return article dicts:
    - title: str
    - url: str
    - published_at: 'YYYY-MM-DD' (if you can find a date; else today)
    - raw_html: full HTML of the article page
    """
    # Easy-to-edit CSS selectors and patterns
    ARCHIVE_LINK_PATTERNS = ['/p/', '/posts/', '/blog/', '/article/', '/post/']
    ARCHIVE_LINK_SELECTORS = ['a[href*="/p/"]', 'a[href*="/posts/"]', 'a[href*="/blog/"]', 'a']

    # Date extraction selectors for individual article pages
    DATE_SELECTORS = [
        'time[datetime]',
        'time[data-time]',
        '.post-date',
        '.published',
        '.date',
        '[class*="date"]',
        '.post-meta time',
        '.entry-date'
    ]

    # Content extraction selectors for individual article pages
    CONTENT_SELECTORS = [
        'article',
        '.post-content',
        '.entry-content',
        '.content',
        'main[role="main"]',
        'main',
        '.post-body',
        '.article-content'
    ]

    try:
        print(f"Fetching archive page: {archive_url}")
        response = requests.get(archive_url, headers=HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        article_links = []

        # Find all potential article links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')

            # Check if href matches any of our patterns
            if any(pattern in href for pattern in ARCHIVE_LINK_PATTERNS):
                # Build absolute URL
                if href.startswith('/'):
                    # Extract base domain from archive_url
                    from urllib.parse import urlparse
                    parsed = urlparse(archive_url)
                    full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue

                if full_url not in article_links:
                    article_links.append(full_url)

        print(f"Found {len(article_links)} potential article links in archive")

        # Limit the number of links we'll process if specified
        if limit:
            article_links = article_links[:limit]

        articles = []

        for i, url in enumerate(article_links, 1):
            try:
                print(f"Fetching article {i}/{len(article_links)}: {url}")
                article_response = requests.get(url, headers=HEADERS)
                article_response.raise_for_status()

                article_soup = BeautifulSoup(article_response.text, 'html.parser')

                # Extract title
                title_elem = article_soup.find('title')
                if not title_elem:
                    title_elem = article_soup.find('h1')
                title = title_elem.get_text().strip() if title_elem else "Untitled"
                # Clean up title (remove site name suffixes)
                if ' | ' in title:
                    title = title.split(' | ')[0].strip()
                if ' - ' in title:
                    title = title.split(' - ')[0].strip()

                # Extract published date
                published_at = datetime.now().strftime("%Y-%m-%d")

                for selector in DATE_SELECTORS:
                    date_elem = article_soup.select_one(selector)
                    if date_elem:
                        date_text = (date_elem.get('datetime') or
                                   date_elem.get('data-time') or
                                   date_elem.get_text() or "").strip()
                        if date_text:
                            # Try multiple date formats
                            date_formats = [
                                "%Y-%m-%d",
                                "%Y-%m-%dT%H:%M:%S",
                                "%Y-%m-%dT%H:%M:%S%z",
                                "%Y-%m-%dT%H:%M:%SZ",
                                "%B %d, %Y",
                                "%b %d, %Y",
                                "%m/%d/%Y",
                                "%d/%m/%Y"
                            ]

                            for fmt in date_formats:
                                try:
                                    # Handle timezone info by taking only date portion
                                    clean_date_text = date_text.split('T')[0] if 'T' in date_text else date_text
                                    if ' ' in clean_date_text and clean_date_text.count(' ') >= 2:
                                        # For formats like "December 13, 2023"
                                        parsed = datetime.strptime(clean_date_text, fmt)
                                    else:
                                        parsed = datetime.strptime(clean_date_text, fmt)
                                    published_at = parsed.strftime("%Y-%m-%d")
                                    break
                                except ValueError:
                                    continue
                            if published_at != datetime.now().strftime("%Y-%m-%d"):
                                break

                # Filter by date if since is provided
                if since:
                    try:
                        article_date = datetime.strptime(published_at, "%Y-%m-%d")
                        since_date = datetime.strptime(since, "%Y-%m-%d")
                        if article_date < since_date:
                            print(f"  Skipping (too old): {title} ({published_at})")
                            continue
                    except ValueError:
                        # If date parsing fails, include the article
                        pass

                # Extract main content
                raw_html = ""
                for selector in CONTENT_SELECTORS:
                    content_elem = article_soup.select_one(selector)
                    if content_elem:
                        raw_html = str(content_elem)
                        break

                if not raw_html:
                    # Fallback: get body content
                    body = article_soup.find('body')
                    raw_html = str(body) if body else ""

                article = {
                    "title": title,
                    "url": url,
                    "published_at": published_at,
                    "raw_html": raw_html
                }

                articles.append(article)
                print(f"  ✓ Added: {title} ({published_at})")

            except requests.RequestException as e:
                print(f"  ✗ Error fetching article {url}: {e}")
                continue
            except Exception as e:
                print(f"  ✗ Error processing article {url}: {e}")
                continue

        print(f"Successfully fetched {len(articles)} articles from archive")
        return articles

    except requests.RequestException as e:
        print(f"Error fetching archive page: {e}")
        return []
    except Exception as e:
        print(f"Error parsing archive page: {e}")
        return []


def fetch_paginated_posts(base_url: str, since: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Fetch articles from paginated Ghost CMS tag pages.

    Args:
        base_url: Ghost tag page URL like "https://www.marcusbpeter.com/t/posts"
        since: Only include posts after this date (YYYY-MM-DD)
        limit: Maximum number of articles to fetch

    Returns:
        List of article dicts with title, url, published_at, raw_html
    """
    MAX_PAGES = 200  # Prevent infinite loops
    all_articles = []
    seen_urls = set()  # Track duplicates to detect loops

    # Start with base URL (page 1)
    current_page = 1

    print(f"Starting paginated fetch from: {base_url}")

    while current_page <= MAX_PAGES:
        # Construct page URL
        if current_page == 1:
            page_url = base_url
        else:
            page_url = f"{base_url}/page/{current_page}"

        print(f"Fetching page {current_page}: {page_url}")

        try:
            response = requests.get(page_url, headers=HEADERS)

            # Stop if page doesn't exist
            if response.status_code == 404:
                print(f"  Page {current_page} returned 404, stopping pagination")
                break

            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            page_links = []

            # Extract article links from this page (same logic as get_article_links)
            article_links = soup.find_all('a', href=True)

            for link in article_links:
                href = link.get('href')
                if href and ('/t/' in href or '/posts/' in href or '/p/' in href):
                    if href.startswith('/'):
                        full_url = f"https://www.marcusbpeter.com{href}"
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        continue

                    if 'marcusbpeter.com' in full_url and full_url not in seen_urls:
                        page_links.append(full_url)
                        seen_urls.add(full_url)

            # Stop if no new articles found on this page
            if not page_links:
                print(f"  No new articles found on page {current_page}, stopping pagination")
                break

            print(f"  Found {len(page_links)} articles on page {current_page}")

            # Process each article on this page
            for i, url in enumerate(page_links, 1):
                try:
                    print(f"    Fetching article {i}/{len(page_links)}: {url}")
                    article = fetch_article(url)

                    # Apply date filter
                    if since:
                        try:
                            article_date = datetime.strptime(article["published_at"], "%Y-%m-%d")
                            since_date = datetime.strptime(since, "%Y-%m-%d")
                            if article_date < since_date:
                                print(f"      Skipping (too old): {article['title']} ({article['published_at']})")
                                continue
                        except ValueError:
                            # If date parsing fails, include the article
                            pass

                    all_articles.append(article)
                    print(f"      ✓ Added: {article['title']} ({article['published_at']})")

                    # Apply limit check
                    if limit and len(all_articles) >= limit:
                        print(f"  Reached limit of {limit} articles, stopping")
                        return all_articles

                except Exception as e:
                    print(f"      ✗ Error fetching article {url}: {e}")
                    continue

            current_page += 1

        except requests.RequestException as e:
            print(f"  Error fetching page {current_page}: {e}")
            break
        except Exception as e:
            print(f"  Error processing page {current_page}: {e}")
            break

    print(f"Pagination complete. Fetched {len(all_articles)} total articles across {current_page - 1} pages")
    return all_articles


def fetch_deacon_articles(since: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Fetch articles from Deacon Harold's WordPress RSS feed.

    Returns a list of dicts with:
    - title: str
    - url: str
    - published_at: "YYYY-MM-DD"
    - raw_html: str
    """
    return fetch_wordpress_rss(DEACON_RSS_URL, "Deacon Harold", since=since, limit=limit)


def fetch_ray_articles(since: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Fetch articles from Dr. Ray's WordPress site.
    Uses RSS feed to get article URLs, then fetches full HTML content for each article.

    Returns a list of dicts with:
    - title: str
    - url: str
    - published_at: "YYYY-MM-DD"
    - raw_html: str (full article content, not just RSS summary)
    """
    try:
        print(f"Fetching Dr. Ray RSS feed: {RAY_RSS_URL}")
        response = requests.get(RAY_RSS_URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, features="xml")
        items = soup.find_all('item')

        articles = []

        for item in items:
            # Extract URL from RSS
            link_elem = item.find('link')
            url = link_elem.get_text().strip() if link_elem else ""
            if not url:
                continue

            # Extract published date from RSS
            pub_date_elem = item.find('pubDate')
            published_at = datetime.now().strftime("%Y-%m-%d")
            if pub_date_elem:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(pub_date_elem.get_text().strip())
                    published_at = pub_date.strftime("%Y-%m-%d")
                except:
                    pass

            # Apply date filter early if possible
            if since:
                try:
                    article_date = datetime.strptime(published_at, "%Y-%m-%d")
                    since_date = datetime.strptime(since, "%Y-%m-%d")
                    if article_date < since_date:
                        continue
                except ValueError:
                    pass

            # Now fetch the full article HTML content
            try:
                print(f"  Fetching full article: {url}")
                article = fetch_article(url)

                # Override the published_at with RSS date if we got one
                if pub_date_elem:
                    article["published_at"] = published_at

                articles.append(article)
                print(f"  ✓ Fetched from Dr. Ray: {article['title']}")

                # Apply limit
                if limit and len(articles) >= limit:
                    break

            except Exception as e:
                print(f"  ✗ Error fetching article {url}: {e}")
                continue

        print(f"Successfully fetched {len(articles)} articles from Dr. Ray")
        return articles

    except Exception as e:
        print(f"Error fetching Dr. Ray RSS feed: {e}")
        return []


def fetch_wordpress_rss(rss_url: str, source_name: str, since: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Generic WordPress RSS fetcher for Catholic sources.

    Args:
        rss_url: WordPress RSS feed URL
        source_name: Name for logging
        since: Only include posts after this date (YYYY-MM-DD)
        limit: Maximum number of articles to fetch

    Returns:
        List of article dicts with title, url, published_at, raw_html
    """
    try:
        print(f"Fetching {source_name} RSS feed: {rss_url}")
        response = requests.get(rss_url, headers=HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, features="xml")
        items = soup.find_all('item')

        articles = []
        for item in items:
            # Extract title
            title_elem = item.find('title')
            title = title_elem.get_text().strip() if title_elem else "Untitled"

            # Extract URL
            link_elem = item.find('link')
            url = link_elem.get_text().strip() if link_elem else ""

            # Extract published date
            pub_date_elem = item.find('pubDate')
            published_at = datetime.now().strftime("%Y-%m-%d")

            if pub_date_elem:
                try:
                    # Parse RFC 2822 format used in RSS
                    pub_date_str = pub_date_elem.get_text().strip()
                    parsed_date = parsedate_to_datetime(pub_date_str)
                    # Convert to naive datetime for consistency
                    if parsed_date.tzinfo:
                        parsed_date = parsed_date.replace(tzinfo=None)
                    published_at = parsed_date.strftime("%Y-%m-%d")
                except Exception:
                    # Fallback to current date if parsing fails
                    pass

            # Filter by date if since is provided
            if since:
                try:
                    article_date = datetime.strptime(published_at, "%Y-%m-%d")
                    since_date = datetime.strptime(since, "%Y-%m-%d")
                    if article_date < since_date:
                        continue
                except ValueError:
                    # If date parsing fails, include the article
                    pass

            # Extract content - WordPress typically uses content:encoded
            content_elem = item.find('content:encoded') or item.find('description')
            raw_html = ""
            if content_elem:
                raw_html = content_elem.get_text() if content_elem.string else str(content_elem)

            article = {
                "title": title,
                "url": url,
                "published_at": published_at,
                "raw_html": raw_html
            }

            articles.append(article)
            print(f"  Fetched from {source_name}: {title}")

            # Apply limit if specified
            if limit and len(articles) >= limit:
                break

        print(f"Successfully fetched {len(articles)} articles from {source_name}")
        return articles

    except requests.RequestException as e:
        print(f"Error fetching {source_name} RSS feed: {e}")
        return []
    except Exception as e:
        print(f"Error parsing {source_name} RSS feed: {e}")
        return []


def fetch_single_url(target_url: str):
    """
    Fetch a single arbitrary URL and return it as one 'article' dict,
    so the rest of the pipeline (cleaner -> scorer -> exporter) just works.
    """
    print(f"Fetching single URL: {target_url}")

    # Try browser headers first, fallback to basic headers
    try:
        resp = requests.get(target_url, headers=BROWSER_HEADERS, timeout=10)
        resp.raise_for_status()
    except:
        resp = requests.get(target_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    # Try title tag, fall back to URL
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else target_url

    # You can't reliably get real publish dates from arbitrary pages,
    # so just use "today" for now.
    published_at = datetime.today().strftime("%Y-%m-%d")

    return [{
        "title": title,
        "url": target_url,
        "published_at": published_at,
        "raw_html": html,
    }]


# Rename the original function for clarity but keep it available
def fetch_site_articles(base_url: str, limit: int | None = None, since: str | None = None) -> list[dict]:
    """Fetch multiple articles from the website (original implementation)."""
    return fetch_articles(base_url, limit, since)