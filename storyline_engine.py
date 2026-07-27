import difflib
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

from data.storyline_fetcher import CACHE_DIR, fetch_item7, item7_cache_path

load_dotenv()

MAX_SUMMARY_INPUT_CHARS = 100_000
SUMMARY_SYSTEM_PROMPT = """You are a financial analyst summarizing SEC 10-K Management Discussion and Analysis (Item 7) content for investors.

Write a concise summary that covers:
- Key business developments and strategic shifts
- Revenue, margin, and earnings drivers, including specific numbers when present
- Major risks or headwinds mentioned
- Notable year-over-year changes when the input appears to be a diff

Use short bullet points. Be factual and only use numbers that appear in the source text."""


def load_item7_cache(ticker: str, year: int) -> dict | None:
    """Load cached Item 7 blocks for a ticker and year."""
    path = item7_cache_path(ticker, year)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as cache_file:
        return json.load(cache_file)


def load_item7(ticker: str, year: int, force_refresh: bool = False) -> dict | None:
    """Load Item 7 from cache, fetching and caching from SEC when missing."""
    if not force_refresh:
        cached = load_item7_cache(ticker, year)
        if cached is not None:
            return cached
    return fetch_item7(ticker, year)


def rows_to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    if not headers:
        return ""

    width = len(headers)
    padded_rows = [row + [""] * (width - len(row)) for row in rows]
    separator = ["---"] * width
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in padded_rows)
    return "\n".join(lines)


def table_block_to_markdown(block: dict) -> str:
    return rows_to_markdown(block.get("headers", []), block.get("rows", []))


def blocks_to_llm_text(blocks: list[dict]) -> str:
    """Serialize structured Item 7 blocks into markdown for LLM prompts."""
    parts = []
    for block in blocks:
        block_type = block.get("type")
        if block_type == "paragraph":
            text = block.get("text", "").strip()
            if text:
                parts.append(text)
        elif block_type == "table":
            markdown = table_block_to_markdown(block)
            if markdown:
                parts.append(markdown)
            else:
                fallback = block.get("text", "").strip()
                if fallback:
                    parts.append(fallback)
    return "\n\n".join(parts)


def text_diff(text1: str, text2: str) -> str:
    """Return unified diff lines showing changes from text2 to text1."""
    diff_lines = difflib.unified_diff(
        text2.splitlines(),
        text1.splitlines(),
        fromfile="prior",
        tofile="current",
        lineterm="",
    )
    return "\n".join(diff_lines)


def get_item7_llm_text(ticker: str, year: int, force_refresh: bool = False) -> str | None:
    """Load Item 7 for a ticker/year and serialize it for LLM consumption."""
    item7 = load_item7(ticker, year, force_refresh=force_refresh)
    if item7 is None:
        return None
    return blocks_to_llm_text(item7["blocks"])


def reduce_text(ticker: str, year: int) -> str | None:
    """Return Item 7 changes versus the prior year, ready for LLM summarization."""
    current = load_item7(ticker, year)
    if current is None:
        return None

    current_text = blocks_to_llm_text(current["blocks"])
    prior = load_item7(ticker, year - 1)
    if prior is None:
        return current_text

    prior_text = blocks_to_llm_text(prior["blocks"])
    diff = text_diff(current_text, prior_text)
    return diff if diff.strip() else current_text


def _truncate_for_llm(text: str, max_chars: int = MAX_SUMMARY_INPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars].rsplit("\n\n", 1)[0]
    return (
        f"{truncated}\n\n"
        "[Input truncated due to length. Summary is based on the beginning of the document.]"
    )


def summarize_text(text: str) -> str:
    """Summarize Item 7 or diff text using an LLM."""
    if not text or not text.strip():
        return ""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt_text = _truncate_for_llm(text)

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
    )

    summary = response.choices[0].message.content
    return summary.strip() if summary else ""


def summary_cache_path(ticker: str, year: int) -> str:
    return os.path.join(CACHE_DIR, f"{ticker.upper()}_item7_summary_{year}.json")


def load_summary_cache(ticker: str, year: int) -> dict | None:
    """Load a cached Item 7 summary for a ticker and year."""
    path = summary_cache_path(ticker, year)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as cache_file:
        return json.load(cache_file)


def save_summary(ticker: str, year: int, summary: str) -> dict:
    """Save an Item 7 summary to the local cache."""
    payload = {
        "ticker": ticker.upper(),
        "year": year,
        "summary": summary,
        "summarized_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(summary_cache_path(ticker, year), "w", encoding="utf-8") as cache_file:
        json.dump(payload, cache_file, default=str)
    return payload


def summarize_item7(ticker: str, year: int, force_refresh: bool = False) -> dict | None:
    """Load Item 7, diff against the prior year when available, and return an LLM summary."""
    if not force_refresh:
        cached = load_summary_cache(ticker, year)
        if cached is not None:
            return cached

    text = reduce_text(ticker, year)
    if text is None:
        return None

    summary = summarize_text(text)
    return save_summary(ticker, year, summary)