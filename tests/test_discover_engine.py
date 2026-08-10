"""
Tests for discover_engine.py's quiz -> risk tier logic.

Run with: pytest tests/test_discover_engine.py -v
"""

from discover_engine import (
    compute_risk_tier,
    get_suggestions,
    rank_by_score,
    CURATED_UNIVERSE,
    RISK_TIERS,
    SECTOR_OPTIONS,
)


def test_consistent_conservative_answers():
    tier = compute_risk_tier("Play it safe", "Sell to stop the loss", "Just exploring")
    assert tier == "Conservative"


def test_consistent_growth_answers():
    tier = compute_risk_tier(
        "I'm fine with big swings for bigger potential gains",
        "Buy more at the lower price",
        "Just exploring",
    )
    assert tier == "Growth"


def test_moderate_agreement_averages_to_balanced():
    tier = compute_risk_tier(
        "Some ups and downs are fine",
        "Hold and wait it out",
        "Just exploring",
    )
    assert tier == "Balanced"


def test_inconsistent_answers_trust_the_more_conservative_one():
    """
    "Play it safe" (1) + "Buy more on the dip" (3) disagree sharply -
    the more conservative answer should win, not the average (which
    would incorrectly land on "Balanced").
    """
    tier = compute_risk_tier("Play it safe", "Buy more at the lower price", "Just exploring")
    assert tier == "Conservative"


def test_goal_nudges_tier_down_but_not_past_conservative():
    # Already Conservative from consistent safe answers - "Steady &
    # stable" shouldn't push it off the end of the scale.
    tier = compute_risk_tier("Play it safe", "Sell to stop the loss", "Steady & stable")
    assert tier == "Conservative"


def test_goal_nudges_balanced_down_to_conservative():
    tier = compute_risk_tier(
        "Some ups and downs are fine",
        "Hold and wait it out",
        "Steady & stable",
    )
    assert tier == "Conservative"


def test_goal_nudges_balanced_up_to_growth():
    tier = compute_risk_tier(
        "Some ups and downs are fine",
        "Hold and wait it out",
        "Long-term growth",
    )
    assert tier == "Growth"


def test_goal_nudges_tier_up_but_not_past_growth():
    tier = compute_risk_tier(
        "I'm fine with big swings for bigger potential gains",
        "Buy more at the lower price",
        "Long-term growth",
    )
    assert tier == "Growth"


def test_unrecognized_answers_fall_back_to_balanced():
    tier = compute_risk_tier("garbage", "garbage", "Just exploring")
    assert tier == "Balanced"


def test_get_suggestions_returns_curated_pool():
    suggestions = get_suggestions("Technology", "Conservative")
    assert suggestions == CURATED_UNIVERSE["Technology"]["Conservative"]


def test_get_suggestions_respects_max_results():
    suggestions = get_suggestions("Technology", "Growth", max_results=2)
    assert len(suggestions) == 2


def test_get_suggestions_unknown_sector_returns_empty():
    assert get_suggestions("Not A Real Sector", "Balanced") == []


def test_every_sector_option_maps_to_a_covered_sector():
    """Every quiz sector label must resolve to a sector actually in CURATED_UNIVERSE."""
    for real_sector in SECTOR_OPTIONS.values():
        assert real_sector in CURATED_UNIVERSE


def test_every_sector_has_all_three_tiers_populated():
    for sector, tiers in CURATED_UNIVERSE.items():
        for tier in RISK_TIERS:
            assert tier in tiers, f"{sector} is missing the {tier} tier"
            assert len(tiers[tier]) > 0, f"{sector}/{tier} has no tickers"


def test_pools_are_wide_enough_to_actually_rank():
    """
    The whole point of the lite version is a real pool to rank, not
    a fixed short display list - this guards against silently
    shrinking it.
    """
    for sector, tiers in CURATED_UNIVERSE.items():
        for tier, tickers in tiers.items():
            assert len(tickers) >= 16, f"{sector}/{tier} has only {len(tickers)} candidates"


def test_no_duplicate_tickers_within_a_cell():
    for sector, tiers in CURATED_UNIVERSE.items():
        for tier, tickers in tiers.items():
            assert len(set(tickers)) == len(tickers), f"{sector}/{tier} has duplicate tickers"


def test_no_ticker_appears_in_two_tiers_of_the_same_sector():
    """A ticker can't be both Conservative and Growth within one sector."""
    for sector, tiers in CURATED_UNIVERSE.items():
        seen = set()
        for tier, tickers in tiers.items():
            overlap = seen & set(tickers)
            assert not overlap, f"{sector} has {overlap} in more than one tier"
            seen |= set(tickers)


def test_no_ticker_appears_in_two_sectors():
    """These lists are hand-maintained, so cross-sector dupes are easy to introduce."""
    sector_of = {}
    for sector, tiers in CURATED_UNIVERSE.items():
        for tickers in tiers.values():
            for ticker in tickers:
                if ticker in sector_of:
                    assert sector_of[ticker] == sector, (
                        f"{ticker} appears in both {sector_of[ticker]} and {sector}"
                    )
                sector_of[ticker] = sector


def test_get_suggestions_without_max_results_returns_full_pool():
    assert get_suggestions("Technology", "Conservative") == CURATED_UNIVERSE["Technology"]["Conservative"]


# ----------------------------------------------------------
# rank_by_score
# ----------------------------------------------------------


def test_rank_by_score_orders_highest_first():
    scores = {"AAA": 50, "BBB": 90, "CCC": 70}
    ranked = rank_by_score(["AAA", "BBB", "CCC"], score_fn=scores.get)
    assert [ticker for ticker, _ in ranked] == ["BBB", "CCC", "AAA"]


def test_rank_by_score_respects_max_results():
    scores = {"AAA": 50, "BBB": 90, "CCC": 70, "DDD": 60}
    ranked = rank_by_score(["AAA", "BBB", "CCC", "DDD"], score_fn=scores.get, max_results=2)
    assert [ticker for ticker, _ in ranked] == ["BBB", "CCC"]


def test_rank_by_score_puts_missing_scores_last_not_dropped():
    scores = {"AAA": 50, "BBB": None, "CCC": 70}
    ranked = rank_by_score(["AAA", "BBB", "CCC"], score_fn=scores.get, max_results=3)
    tickers = [ticker for ticker, _ in ranked]
    assert tickers == ["CCC", "AAA", "BBB"]  # BBB (None) goes last, not dropped


def test_rank_by_score_preserves_score_values_in_output():
    scores = {"AAA": 50, "BBB": 90}
    ranked = rank_by_score(["AAA", "BBB"], score_fn=scores.get)
    assert dict(ranked) == {"AAA": 50, "BBB": 90}


def test_rank_by_score_empty_input_returns_empty():
    assert rank_by_score([], score_fn=lambda t: 100) == []