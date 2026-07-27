import re

from bs4 import BeautifulSoup, NavigableString, Tag
from edgar import Company

ITEM7_HEADER = re.compile(
    r"^\s*item\s*7[\.\:\-\s].*(?:management|discussion|analysis|md\s*&\s*a|financial\s+condition|results\s+of\s+operations)",
    re.I,
)
ITEM7_HEADER_LOOSE = re.compile(r"^\s*item\s*7[\.\:\-\s]", re.I)
ITEM7_TEXT = re.compile(r"item\s*7", re.I)
ITEM_END = re.compile(r"^\s*item\s*(7a|8)[\.\:\-\s]", re.I)

BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th"}
INLINE_TAGS = {"span", "a", "b", "strong", "i", "em", "font", "u"}


def get_tenK(ticker: str, year: int):
    """Fetch the 10-k

    Args:
        ticker (str): company's ticker
        date (str): date of the 10-k filing
    """
    company = Company(ticker)

    return company.get_filings(year=year, form="10-K")


def _is_inside_table(node) -> bool:
    """Check if the node is inside a table"""
    return node.find_parent("table") is not None


def _get_block_element(tag: Tag) -> Tag:
    """Get the block element of the tag"""
    block = tag
    while block and block.name in INLINE_TAGS:
        block = block.parent
    return block


def _at_or_past_end(el, end_el: Tag | None) -> bool:
    """Check if the element is at or past the end of the section"""
    if end_el is None:
        return False
    if el is end_el:
        return True
    if isinstance(el, NavigableString):
        return end_el in el.parents
    return False


def _find_item7_start(soup: BeautifulSoup) -> Tag | None:
    """Find the first Item 7 header outside of tables (skips the TOC)."""
    for text_node in soup.find_all(string=ITEM7_TEXT):
        # Skip TOC item 7 headers
        if _is_inside_table(text_node):
            continue

        block = _get_block_element(text_node.parent)
        block_text = block.get_text(" ", strip=True)
        if ITEM7_HEADER.match(block_text) or ITEM7_HEADER_LOOSE.match(block_text):
            return block

    return None


def _find_item7_end(start_el: Tag) -> Tag | None:
    """Find where Item 7 ends (Item 7A or Item 8), ignoring table content."""
    for el in start_el.next_elements:
        if isinstance(el, NavigableString) and _is_inside_table(el):
            continue
        if isinstance(el, Tag) and el.name == "table":
            continue

        if isinstance(el, NavigableString):
            text = str(el).strip()
            parent = el.parent
        elif isinstance(el, Tag) and el.name in BLOCK_TAGS | INLINE_TAGS | {"a"}:
            text = el.get_text(" ", strip=True)
            parent = el
        else:
            continue

        if len(text) > 300:
            continue
        if ITEM_END.match(text):
            return _get_block_element(parent)

    return None


def _extract_section_text(start_el: Tag, end_el: Tag | None) -> str:
    """Extract Item 7 text. Tables inside the section are kept; TOC tables are not."""
    parts = []
    seen_blocks = {id(start_el)}
    seen_tables = set()

    def add_part(text: str):
        text = re.sub(r"[ \t]+", " ", text).strip()
        if text:
            parts.append(text)

    add_part(start_el.get_text(" ", strip=True))

    for el in start_el.next_elements:
        if _at_or_past_end(el, end_el):
            break

        if isinstance(el, Tag) and el.name == "table":
            table_id = id(el)
            if table_id not in seen_tables:
                seen_tables.add(table_id)
                add_part(el.get_text("\n", strip=True))
            continue

        if isinstance(el, NavigableString):
            if _is_inside_table(el):
                continue

            block = _get_block_element(el.parent)
            if id(block) in seen_blocks:
                continue
            if block.name not in BLOCK_TAGS:
                continue

            seen_blocks.add(id(block))
            add_part(block.get_text(" ", strip=True))

    return "\n\n".join(parts)


def get_item7_text(tenK) -> str | None:
    """Get the text of Item 7 (MD&A) in the 10-K, skipping table-of-contents tables."""
    soup = BeautifulSoup(tenK.html(), "html.parser")

    start_el = _find_item7_start(soup)
    if start_el is None:
        return None

    end_el = _find_item7_end(start_el)
    return _extract_section_text(start_el, end_el)


def upload_items(filepath: str):
    """Upload the items to cache
    Args:
        file_path (str): path to the file containing the items
    """
    pass
