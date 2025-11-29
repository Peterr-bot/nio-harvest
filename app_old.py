import streamlit as st
import json
import pandas as pd
import base64
import pathlib
from datetime import date
from main import run_harvest

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

st.set_page_config(
    page_title="Catholic Quote Harvester",
    page_icon="✝️",
    layout="wide",
)

set_background()  # Auto-detect any image in assets/

st.title("Catholic Quote Harvester")
st.caption("Extract meaningful quotes from Catholic content sources or any single URL.")

# --- INPUT AREA -------------------------------------------------------------

with st.container():
    col1, col2 = st.columns([1.2, 1])

    with col1:
        preset = st.selectbox(
            "Preset source",
            [
                "Marcus B. Peter (Ghost CMS)",
                "Deacon Harold (RSS)",
                "Dr. Ray Guarendi (RSS)",
            ],
            index=0,
        )

        url = st.text_input(
            "Or paste a single article/page URL "
            "(this will override the preset source):",
            placeholder="https://www.marcusbpeter.com/p/encountering-the-mercy-of-the-father",
        )

    with col2:
        max_articles = st.number_input(
            "Max articles to process (ignored for single URL)",
            min_value=1,
            max_value=200,
            value=10,
            step=1,
        )
        since = st.text_input(
            "Since date (YYYY-MM-DD, optional for presets)",
            value="2020-01-01",
        )

st.divider()

# --- RUN BUTTON + STATUS ----------------------------------------------------

run_btn = st.button("Harvest Quotes", type="primary")

results_container = st.container()
status_placeholder = st.empty()

if run_btn:
    # Decide source
    if url.strip():
        chosen_source = "url"
    else:
        if "Marcus" in preset:
            chosen_source = "ghost"
        elif "Deacon" in preset:
            chosen_source = "deacon"
        else:
            chosen_source = "ray"

    with st.spinner("Harvesting quotes… This may take a minute for large batches."):
        status_placeholder.info(
            f"Source: **{chosen_source}** · "
            + (f"URL mode" if chosen_source == "url" else f"Up to {max_articles} articles since {since}")
        )
        quotes = run_harvest(
            source=chosen_source,
            limit=max_articles,
            since=since if since.strip() else None,
            url=url if chosen_source == "url" else None,
        )

    if not quotes:
        status_placeholder.warning("No qualifying quotes found. Try a later date, more articles, or a different source.")
    else:
        status_placeholder.success(f"Done. Found **{len(quotes)}** quotes.")

        with results_container:
            st.subheader("Harvested Quotes")

            # Light summary
            punch_scores = [q.get("punch_score", 0) for q in quotes]
            st.write(
                f"Average punch score: **{sum(punch_scores)/len(punch_scores):.1f}**  · "
                f"Top score: **{max(punch_scores)}**"
            )

            # Main table view
            show_cols = [
                "punch_score",
                "category",
                "tone",
                "edited_line",
                "tweet_version",
                "card_version",
                "caption_version",
                "source_title",
                "source_url",
            ]
            trimmed = [
                {k: q.get(k) for k in show_cols}
                for q in quotes
            ]
            st.dataframe(trimmed, use_container_width=True, hide_index=True)

            # Download buttons
            col1, col2 = st.columns(2)

            with col1:
                json_str = json.dumps(quotes, indent=2, ensure_ascii=False)
                st.download_button(
                    "📄 Download JSON",
                    data=json_str,
                    file_name=f"quotes_{chosen_source}_{date.today().strftime('%Y-%m-%d')}.json",
                    mime="application/json"
                )

            with col2:
                df = pd.DataFrame(quotes)
                csv_str = df.to_csv(index=False)
                st.download_button(
                    "📊 Download CSV",
                    data=csv_str,
                    file_name=f"quotes_{chosen_source}_{date.today().strftime('%Y-%m-%d')}.csv",
                    mime="text/csv"
                )