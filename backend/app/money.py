"""Geldbeträge werden ausschließlich als ganzzahlige Centbeträge verarbeitet.

Lastenheft 5.3 / 32.5: Geldbeträge dürfen niemals als binäre Gleitkommazahlen
gespeichert oder berechnet werden. Diese Modul kapselt alle Umrechnungen, damit
im übrigen Code keine Float-Arithmetik auf Geld entsteht.

Interne Repräsentation:  int  (Anzahl Cent, z. B. 2,50 € -> 250)
Anzeige/Formatierung:    str  ("2,50 €", deutsches Format)
Parsing von Eingaben:    Decimal (nur an der Systemgrenze, nie für Rechnungen)
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

Cents = int


def euro_to_cents(value: str | int | Decimal) -> Cents:
    """Wandelt einen Euro-Betrag in ganzzahlige Cent um.

    Akzeptiert "2,50", "2.50", 2 oder Decimal. Es wird kaufmännisch gerundet.
    Float wird bewusst NICHT akzeptiert, um versehentliche Ungenauigkeit zu
    verhindern.
    """
    if isinstance(value, float):
        raise TypeError(
            "float ist für Geldbeträge nicht erlaubt. Bitte str oder Decimal übergeben."
        )
    if isinstance(value, int):
        return value * 100
    text = str(value).strip().replace("\u20ac", "").replace(" ", "").replace("\u00a0", "")
    # Deutsche Schreibweise normalisieren:
    #   "1.000,00" -> Punkt = Tausender, Komma = Dezimal
    #   "2,50"     -> Komma = Dezimal
    #   "2.50"     -> Punkt als Dezimal zulassen
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        dec = Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - defensiver Pfad
        raise ValueError(f"Ungültiger Geldbetrag: {value!r}") from exc
    cents = (dec * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def format_cents(cents: Cents, symbol: str = "€") -> str:
    """Formatiert Cent als deutschen Betrag, z. B. 250 -> '2,50 €'."""
    if not isinstance(cents, int):
        raise TypeError("format_cents erwartet ganzzahlige Cent.")
    sign = "-" if cents < 0 else ""
    whole, rest = divmod(abs(cents), 100)
    body = f"{whole:,}".replace(",", ".")  # Tausenderpunkt
    return f"{sign}{body},{rest:02d}\u00a0{symbol}".strip()


def add(*amounts: Cents) -> Cents:
    """Summiert Centbeträge exakt."""
    total = 0
    for amount in amounts:
        if not isinstance(amount, int):
            raise TypeError("add erwartet ganzzahlige Cent.")
        total += amount
    return total


def multiply(cents: Cents, quantity: int) -> Cents:
    """Multipliziert einen Centbetrag mit einer ganzzahligen Menge."""
    if not isinstance(cents, int) or not isinstance(quantity, int):
        raise TypeError("multiply erwartet ganzzahlige Werte.")
    return cents * quantity
