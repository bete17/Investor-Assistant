"""
Tests for utils.py formatting helpers.

Run with: pytest tests/test_utils.py -v
"""

from utils import format_percent, format_ratio, format_money


def test_format_percent_normal():
    assert format_percent(26.6023) == "26.60%"


def test_format_percent_none():
    assert format_percent(None) == "N/A"


def test_format_percent_negative():
    assert format_percent(-5.5) == "-5.50%"


def test_format_ratio_normal():
    assert format_ratio(0.8034) == "0.80"


def test_format_ratio_none():
    assert format_ratio(None) == "N/A"


def test_format_money_billions():
    assert format_money(26_730_000_000) == "$26.73B"


def test_format_money_millions():
    assert format_money(4_500_000) == "$4.50M"


def test_format_money_thousands():
    assert format_money(2_500) == "$2.50K"


def test_format_money_small_number():
    assert format_money(42.5) == "$42.50"


def test_format_money_negative():
    assert format_money(-1_000_000_000) == "-$1.00B"


def test_format_money_none():
    assert format_money(None) == "N/A"


def test_format_money_trillions():
    assert format_money(3_100_000_000_000) == "$3.10T"