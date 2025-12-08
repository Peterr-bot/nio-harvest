# scorer.py
import json
from typing import Optional, Dict, Any

from ai_core import get_openai_client
from config import MODEL_NAME

# Don't initialize client at import time - use lazy loading

SYSTEM_PROMPT = """
You are a fierce, theologically precise Catholic editor. Your job is to extract
hard-hitting quotes from text. You are looking for lines that feel like they
belong on a brutalist design quote card or a viral X (Twitter) post.

STYLE GUIDELINES:
1. Bold & Concrete: Favor doctrine, reality, consequences, and hope over fluff.
2. No Soft Churchy Fluff: Avoid generic motivational language or vague feel-good phrasing.
3. Theologically Sound: Must be faithful to Magisterial Catholic teaching.
4. Punchy: If a sentence is 90% there, lightly edit it to be 100% impact
   (fix grammar, remove hedging, remove passive voice).

OUTPUT FORMAT:
Return a JSON object with a quotes array, each element following this schema:
{
  "quotes": [
    {
      "is_quote_worthy": boolean,
      "punch_score": integer (1-10),
      "category": "tweet" | "quote_card" | "long_caption",
      "tone": "theology" | "conversion" | "masculine_callout" | "hope" | "warning",
      "edited_line": "The final polished quote text",
      "tweet_version": "Short version < 240 chars",
      "card_version": "Very short version, 1-2 lines max",
      "caption_version": "2-4 line version that can be used as an IG caption"
    }
  ]
}

Extract up to 3 of the best quotes from each text chunk. If no quotes are worth extracting, return an empty quotes array.
"""


def score_chunk(chunk_text: str) -> Optional[list[Dict[str, Any]]]:
    """
    Sends a text chunk to the LLM and returns a list of quote dicts,
    or None if anything goes wrong.
    """
    try:
        # Lazy load client when actually needed
        client = get_openai_client()
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Analyze this text and extract up to 3 of the best quotes:\n\n" + chunk_text
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,  # lower for consistent structure
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # Extract quotes array, return empty list if missing or malformed
        quotes = data.get("quotes", [])
        if not isinstance(quotes, list):
            print(f"[!] Malformed quotes field in response: {quotes}")
            return []

        return quotes

    except json.JSONDecodeError as e:
        print(f"[!] JSON parse error in score_chunk: {e}")
        print(f"[!] Raw content: {content}")
        return None
    except Exception as e:
        print(f"[!] LLM error in score_chunk: {e}")
        print(f"[!] Error type: {type(e).__name__}")
        import traceback
        print(f"[!] Full traceback: {traceback.format_exc()}")
        return None