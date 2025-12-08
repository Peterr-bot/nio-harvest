import streamlit as st
import pandas as pd
import base64
import pathlib
import requests
import json
import os
from datetime import datetime, date

from config import BASE_URL, MIN_PUNCH_SCORE
from fetcher import (
    fetch_paginated_posts,   # Marcus (Ghost pagination)
    fetch_single_url,        # Single arbitrary URL
    fetch_ray_articles,      # Dr. Ray (RSS → full HTML)
    fetch_deacon_articles,   # Deacon Harold (RSS → full HTML)
)
from cleaner import clean_and_chunk
from scorer import score_chunk
from ai_core import test_streamlit_secrets

# Slack integration
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_quotes_to_slack(quotes: list[dict], limit: int = 5) -> None:
    """Send top N quotes to Slack via Incoming Webhook."""

    with st.spinner("Sending to Slack..."):
        # Validate inputs
        if not SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL == "":
            st.error("❌ SLACK_WEBHOOK_URL is not configured")
            return

        if not quotes:
            st.warning("⚠️ No quotes to send")
            return

        try:
            # Take top quotes by punch_score
            top_quotes = sorted(
                quotes,
                key=lambda q: q.get("punch_score", 0),
                reverse=True
            )[:limit]

            if not top_quotes:
                st.warning("⚠️ No qualifying quotes found")
                return

            # Build payload - simplified format
            quote_lines = []
            for i, q in enumerate(top_quotes, 1):
                line = q.get("edited_line", "").strip()
                score = q.get("punch_score", "")

                if line:  # Only add if we have actual content
                    quote_lines.append(f"{i}. *{line}* (score: {score})")

            if not quote_lines:
                st.warning("⚠️ No valid quote content found")
                return

            # Simple, clean message
            message_text = "✝️ *Nio Harvest Results*\n\n" + "\n\n".join(quote_lines)

            # Minimal payload to reduce issues
            payload = {"text": message_text}

            # Add headers for better compatibility
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Nio-Harvest/1.0"
            }

            # Make request with explicit settings
            response = requests.post(
                SLACK_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=15,
                verify=True  # Ensure SSL verification
            )

            if response.status_code == 200:
                st.success(f"✅ Successfully sent {len(top_quotes)} quotes to Slack!")
            else:
                st.error(f"❌ Slack API error: {response.status_code} - {response.text}")

        except requests.exceptions.Timeout:
            st.error("❌ Request timed out - Slack may be unreachable")
        except requests.exceptions.ConnectionError:
            st.error("❌ Connection error - Check your internet connection")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Network error: {str(e)}")
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")
            # Only show traceback in debug mode
            with st.expander("Debug traceback"):
                import traceback
                st.code(traceback.format_exc())

def set_background(image_path: str = None) -> None:
    """Set a full-page background image using a local file."""
    # If no path specified, use any image found in assets/
    if not image_path:
        assets_dir = pathlib.Path("assets")
        if assets_dir.exists():
            image_files = list(assets_dir.glob("*.[jJ][pP][gG]")) + list(assets_dir.glob("*.[jJ][pP][eE][gG]")) + list(assets_dir.glob("*.[pP][nN][gG]"))
            if image_files:
                image_path = str(image_files[0])
            else:
                return
        else:
            return

    img_path = pathlib.Path(image_path)
    if not img_path.exists():
        st.warning(f"Background image not found: {img_path}")
        return

    with open(img_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        .stApp .block-container {{
            background-color: rgba(0, 0, 0, 0.72);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            border-radius: 16px;
            padding: 2rem 2.5rem;
            margin-top: 2rem;
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.55);
        }}

        .stButton>button {{
            border-radius: 999px;
            border: none;
            padding: 0.6rem 1.6rem;
            font-weight: 600;
            background: linear-gradient(45deg, #4A90E2, #7BB3F0);
            color: white;
            transition: all 0.2s ease-out;
        }}

        .stButton>button:hover {{
            background: linear-gradient(45deg, #357ABD, #6BA6E3);
            transform: translateY(-1px);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------- Core pipeline logic (no file export, pure in-memory) ----------

def run_harvest(source: str,
                url: str | None,
                since: str | None,
                limit: int | None) -> list[dict]:
    """
    Run the quote harvester for the selected source.
    Returns a list of quote dicts (same shape as your JSON export).
    """

    # 1) Fetch articles
    try:
        if source == "marcus_all":
            st.write(f"Fetching Marcus posts from: {BASE_URL}")
            articles = fetch_paginated_posts(BASE_URL, limit=limit, since=since)

        elif source == "single_url":
            if not url:
                st.error("You must provide a URL for 'Single URL' mode.")
                return []
            st.write(f"Fetching single URL: {url}")
            articles = fetch_single_url(url)

        elif source == "ray":
            st.write("Fetching articles from Dr. Ray RSS")
            articles = fetch_ray_articles(since=since, limit=limit)

        elif source == "deacon":
            st.write("Fetching articles from Deacon Harold RSS")
            articles = fetch_deacon_articles(since=since, limit=limit)

        else:
            st.error(f"Unknown source: {source}")
            return []

    except Exception as e:
        st.error(f"❌ Error fetching articles: {str(e)}")
        return []

    st.write(f"Found **{len(articles)}** articles to process")

    # 2) Process articles → chunks → scores
    all_quotes: list[dict] = []

    for idx, article in enumerate(articles, start=1):
        title = article.get("title", "Untitled")
        st.write(f"### Processing {idx}/{len(articles)}: {title}")

        raw_html = article.get("raw_html", "")
        if not raw_html:
            st.write("  · Skipping (no HTML content)")
            continue

        chunks = clean_and_chunk(raw_html)
        st.write(f"  · Generated {len(chunks)} chunks")

        chunk_count = 0
        for chunk in chunks:
            chunk_count += 1
            result = score_chunk(chunk)
            if not result:
                st.write(f"    · Chunk {chunk_count}: No result from AI")
                continue

            # Handle both single dict and list of dicts from scorer
            results = result if isinstance(result, list) else [result]

            for quote_result in results:
                score = quote_result.get("punch_score", 0)
                is_worthy = quote_result.get("is_quote_worthy", False)
                line = quote_result.get("edited_line", "")[:50] + "..."

                st.write(f"    · Chunk {chunk_count}: Score {score}, Worthy: {is_worthy}, '{line}'")

                if not is_worthy:
                    continue

                if score < MIN_PUNCH_SCORE:
                    st.write(f"      → Filtered out (score {score} < {MIN_PUNCH_SCORE})")
                    continue

                # Merge article metadata + model result
                quote_record = {
                    "source_title": article.get("title", ""),
                    "source_url": article.get("url", ""),
                    "published_at": article.get("published_at", ""),
                    **quote_result,
                }
                all_quotes.append(quote_record)
                st.write(f"      → ✅ Added quote!")

    # 3) Deduplicate by edited_line
    seen = set()
    unique_quotes = []
    for q in all_quotes:
        line = q.get("edited_line", "").strip()
        if not line:
            continue
        if line in seen:
            continue
        seen.add(line)
        unique_quotes.append(q)

    return unique_quotes


# ---------- Streamlit UI ----------

st.set_page_config(page_title="Nio Harvest", layout="wide")

# Initialize session state
if "quotes" not in st.session_state:
    st.session_state["quotes"] = []

set_background()  # Auto-detect background image

# Centered Header with logo
logo_path = pathlib.Path("assets/logo/Open-Cab Combine Harvester.G08.2k.png")

# Create centered layout with HTML/CSS
st.markdown("""
<div style="display: flex; flex-direction: column; align-items: center; margin: 2rem 0;">
    <div style="margin-bottom: 1rem;">
""", unsafe_allow_html=True)

# Display centered logo
if logo_path.exists():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.image(str(logo_path), width=140)

# Centered title and subtitle
st.markdown("""
    </div>
    <h1 style="text-align: center; margin: 0; font-size: 3rem; font-weight: bold;">🚜 Nio Harvest</h1>
    <p style="text-align: center; margin: 0.5rem 0 0 0; font-size: 1.1rem; color: #666;">Marcus · Dr. Ray · Deacon Harold · Single URL</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Source & Filters")

    # Test OpenAI key loading
    if st.button("🔧 Test OpenAI Key", help="Validate API key configuration"):
        test_result = test_streamlit_secrets()
        if "✅" in test_result:
            st.success(test_result)
        else:
            st.error(test_result)

    source_label = st.selectbox(
        "Content source",
        [
            "Marcus (all posts)",
            "Single URL",
            "Dr. Ray (RSS)",
            "Deacon Harold (RSS)",
        ],
    )

    if source_label == "Marcus (all posts)":
        source = "marcus_all"
    elif source_label == "Single URL":
        source = "single_url"
    elif source_label == "Dr. Ray (RSS)":
        source = "ray"
    else:
        source = "deacon"

    url_input = None
    if source == "single_url":
        url_input = st.text_input(
            "Article URL",
            placeholder="https://www.marcusbpeter.com/p/encountering-the-mercy-of-the-father",
        )

    since_date = st.date_input(
        "Since date (optional)",
        value=date(2024, 1, 1),
        help="Only include articles published on or after this date.",
    )
    since_str = since_date.strftime("%Y-%m-%d") if since_date else None

    limit = st.number_input(
        "Max articles to process",
        min_value=1,
        max_value=100,
        value=5,
        step=1,
    )

    run_button = st.button("Run Harvester", type="primary")

st.divider()


if run_button:
    try:
        with st.spinner("Running quote harvester..."):
            quotes = run_harvest(
                source=source,
                url=url_input,
                since=since_str,
                limit=int(limit) if limit else None,
            )
        st.session_state["quotes"] = quotes
    except Exception as e:
        st.error(f"❌ Harvester crashed: {str(e)}")
        with st.expander("🔍 Debug details"):
            import traceback
            st.code(traceback.format_exc())
        st.stop()  # Prevent further execution

# Render results from session state (outside run_button block)
quotes = st.session_state.get("quotes", [])

if quotes:
    st.write(f"## Results")
    st.write(f"Found **{len(quotes)}** unique quotes with punch ≥ {MIN_PUNCH_SCORE}")

    # Build DataFrame for display & download
    df = pd.DataFrame(quotes)

    # Reorder columns for sanity
    preferred_cols = [
        "edited_line",
        "punch_score",
        "category",
        "tone",
        "tweet_version",
        "card_version",
        "caption_version",
        "source_title",
        "source_url",
        "published_at",
    ]
    cols = [c for c in preferred_cols if c in df.columns] + [
        c for c in df.columns if c not in preferred_cols
    ]
    df = df[cols]

    st.dataframe(df, use_container_width=True, height=500)

    # Downloads
    csv_data = df.to_csv(index=False).encode("utf-8")
    json_data = df.to_json(orient="records", force_ascii=False, indent=2).encode(
        "utf-8"
    )

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📊 Download CSV",
            data=csv_data,
            file_name=f"catholic_quotes_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
        )
    with c2:
        st.download_button(
            "📄 Download JSON",
            data=json_data,
            file_name=f"catholic_quotes_{datetime.now().strftime('%Y-%m-%d')}.json",
            mime="application/json",
        )

    # Slack integration - Single button using session state
    st.markdown("---")
    if st.button("📤 Send top 5 quotes to Slack", type="secondary"):
        try:
            send_quotes_to_slack(quotes, limit=5)
            st.success("✅ Sent top 5 quotes to Slack.")
        except Exception as e:
            st.error(f"❌ Failed to send to Slack: {e}")

else:
    st.info("No quotes yet. Run the harvester to see results.")