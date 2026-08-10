# --------------------------------------------------
# LOADING SKELETONS
# --------------------------------------------------
# Ghost placeholders rendered while data is being fetched, so pages
# never show an empty region with just a spinner floating in it.
#
# Each helper writes into a container the CALLER owns (usually an
# st.empty() placeholder), so the caller can replace the skeleton
# with real content once loading finishes:
#
#     slot = st.empty()
#     with slot.container():
#         skeleton_card_row(4)
#     data = fetch_something()      # slow
#     slot.empty()                  # skeleton disappears
#     render_real_cards(data)
#
# Styling lives in UI/styles.css under "LOADING SKELETONS" - the
# skeleton dimensions there deliberately mirror the real .kpi-card
# elements so the swap doesn't shift page layout.

import streamlit as st

_CARD_SKELETON = """
<div class="skeleton-card">
    <div class="skeleton-bar skeleton-title"></div>
    <div class="skeleton-bar skeleton-value"></div>
    <div class="skeleton-bar skeleton-status"></div>
    <div class="skeleton-bar skeleton-line"></div>
    <div class="skeleton-bar skeleton-line short"></div>
</div>
"""

_CHART_SKELETON = """
<div class="skeleton-card">
    <div class="skeleton-bar skeleton-title"></div>
    <div class="skeleton-bar skeleton-chart"></div>
</div>
"""


def skeleton_card():
    """One card-shaped placeholder, matching .kpi-card's dimensions."""
    st.markdown(_CARD_SKELETON, unsafe_allow_html=True)


def skeleton_card_row(count):
    """
    A row of `count` card placeholders in equal columns - matching how
    the real cards are laid out via st.columns(), so the skeleton
    occupies the same grid the real content will.
    """
    columns = st.columns(count)
    for column in columns:
        with column:
            skeleton_card()


def skeleton_chart():
    """A chart-shaped placeholder matching the 390px Plotly chart height."""
    st.markdown(_CHART_SKELETON, unsafe_allow_html=True)


def skeleton_bullets(count=6):
    """
    A card containing `count` text-line placeholders - stands in for
    the storyline page's bullet summary while the LLM call runs.
    """
    # Alternating widths so it reads as prose rather than a solid block.
    lines = "".join(
        f'<div class="skeleton-bar skeleton-bullet" style="width: {width}%;"></div>'
        for width in [96, 88, 92, 74, 90, 68, 84, 79][:count]
    )
    st.markdown(
        f'<div class="skeleton-card">{lines}</div>',
        unsafe_allow_html=True,
    )