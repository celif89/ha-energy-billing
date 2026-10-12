"""Czyste funkcje obliczeniowe (bez zależności od Home Assistant)."""
from __future__ import annotations

from typing import Any

_INVALID_STATES = {"unknown", "unavailable", "none", ""}


def parse_number(value: Any) -> float | None:
    """Zamień stan encji na liczbę; obsługuje przecinek dziesiętny (np. "0,50")."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _INVALID_STATES:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def price_per_kwh(price: float, unit: str | None) -> float:
    """Sprowadź cenę do PLN/kWh (cena w PLN/MWh jest dzielona przez 1000)."""
    if unit and "mwh" in unit.lower():
        return price / 1000
    return price


def meter_delta(current: float, previous: float) -> float:
    """Przyrost licznika narastającego; spadek (wymiana/zerowanie licznika) daje 0."""
    return max(0.0, current - previous)


def hourly_revenue(exported: float, imported: float, price: float) -> float:
    """Przychód za godzinę: dodatnie saldo godzinowe × cena."""
    balance = exported - imported
    return balance * price if balance > 0 else 0.0
