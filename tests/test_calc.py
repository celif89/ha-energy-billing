from custom_components.energy_billing.calc import (
    hourly_revenue,
    meter_delta,
    parse_number,
    price_per_kwh,
)


def test_parse_number():
    assert parse_number("0,50") == 0.5
    assert parse_number("12.5") == 12.5
    assert parse_number(3) == 3.0
    for bad in (None, "unknown", "unavailable", "", "abc"):
        assert parse_number(bad) is None


def test_price_per_kwh():
    assert price_per_kwh(0.5, "PLN/kWh") == 0.5
    assert price_per_kwh(0.5, "zł/kWh") == 0.5
    assert price_per_kwh(500, "PLN/MWh") == 0.5
    assert price_per_kwh(0.5, None) == 0.5


def test_meter_delta():
    assert meter_delta(10.5, 10.0) == 0.5
    assert meter_delta(0.2, 1500.0) == 0.0


def test_hourly_revenue():
    assert hourly_revenue(3.0, 1.0, 0.5) == 1.0
    assert hourly_revenue(1.0, 3.0, 0.5) == 0.0
    assert hourly_revenue(3.0, 1.0, -0.1) == -0.2
