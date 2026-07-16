from decimal import Decimal

import pytest

from app import money


def test_euro_to_cents_from_string():
    assert money.euro_to_cents("2,50") == 250
    assert money.euro_to_cents("2.50") == 250
    assert money.euro_to_cents("0,05") == 5
    assert money.euro_to_cents("1.000,00") == 100000


def test_euro_to_cents_from_int_and_decimal():
    assert money.euro_to_cents(3) == 300
    assert money.euro_to_cents(Decimal("4.00")) == 400


def test_float_is_rejected():
    with pytest.raises(TypeError):
        money.euro_to_cents(2.5)


def test_rounding_is_commercial():
    assert money.euro_to_cents("0,005") == 1  # rundet auf
    assert money.euro_to_cents("0,004") == 0


def test_format_cents():
    assert money.format_cents(250) == "2,50\u00a0\u20ac"
    assert money.format_cents(0) == "0,00\u00a0\u20ac"
    assert money.format_cents(-100) == "-1,00\u00a0\u20ac"
    assert money.format_cents(123456) == "1.234,56\u00a0\u20ac"


def test_add_and_multiply_exact():
    total = money.add(250, 250, 100)  # 2x Cola + 1x Pommes (Szenario B ohne Pfand)
    assert total == 600
    assert money.multiply(250, 2) == 500


def test_scenario_b_totals():
    # 2x Cola 2,50 + 2x Flaschenpfand 1,00 + 1x Pommes 4,00 = 11,00 EUR
    artikel = money.add(money.multiply(250, 2), 400)
    pfand = money.multiply(100, 2)
    gesamt = money.add(artikel, pfand)
    assert artikel == 900
    assert pfand == 200
    assert gesamt == 1100
    assert money.format_cents(gesamt) == "11,00\u00a0\u20ac"
