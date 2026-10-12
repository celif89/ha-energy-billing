import logging
from datetime import datetime

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)

from custom_components.energy_billing.const import DOMAIN

from .conftest import EXPORT, IMPORT, PRICE

pytestmark = pytest.mark.usefixtures("warsaw")

KEYS = ("money_daily", "energy_hourly", "energy_daily", "hour_progress")


def at(text: str) -> datetime:
    return dt_util.parse_datetime(f"2026-03-10T{text}+01:00")


async def tick(hass, freezer, text: str) -> None:
    freezer.move_to(at(text))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


def meters(hass, imported, exported, price="0.5", unit="PLN/kWh") -> None:
    hass.states.async_set(IMPORT, imported, {"unit_of_measurement": "kWh"})
    hass.states.async_set(EXPORT, exported, {"unit_of_measurement": "kWh"})
    hass.states.async_set(PRICE, price, {"unit_of_measurement": unit})


def ids(hass) -> dict[str, str]:
    reg = er.async_get(hass)
    return {k: reg.async_get_entity_id("sensor", DOMAIN, f"test_entry_{k}") for k in KEYS}


def value(hass, entity_id):
    state = hass.states.get(entity_id).state
    return state if state in (STATE_UNKNOWN, STATE_UNAVAILABLE) else float(state)


async def setup(hass, freezer, config_entry, start="10:30:00"):
    freezer.move_to(at(start))
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return ids(hass)


async def test_hourly_settlement(hass, freezer, config_entry):
    meters(hass, 100.0, 50.0)
    e = await setup(hass, freezer, config_entry)

    await tick(hass, freezer, "10:59:50")  # pierwszy odczyt bazowy
    assert value(hass, e["energy_hourly"]) == 0.0
    assert value(hass, e["hour_progress"]) == 0.0

    meters(hass, 101.0, 52.0)
    await tick(hass, freezer, "11:20:00")
    assert value(hass, e["hour_progress"]) == 1.0

    meters(hass, 101.5, 54.0)
    await tick(hass, freezer, "11:59:50")
    assert value(hass, e["energy_hourly"]) == 2.5
    assert value(hass, e["energy_daily"]) == 2.5
    assert value(hass, e["money_daily"]) == 1.25
    assert value(hass, e["hour_progress"]) == 0.0

    # Godzina z przewagą poboru: bilans ujemny, zarobek bez zmian.
    meters(hass, 104.0, 54.5, price="0,80")
    await tick(hass, freezer, "12:59:50")
    assert value(hass, e["energy_hourly"]) == -2.0
    assert value(hass, e["energy_daily"]) == 0.5
    assert value(hass, e["money_daily"]) == 1.25

    attrs = hass.states.get(e["energy_hourly"]).attributes
    assert attrs["state_class"] == "total"
    assert dt_util.parse_datetime(attrs["last_reset"]) == at("11:59:50")


async def test_price_in_mwh(hass, freezer, config_entry):
    meters(hass, 100.0, 50.0, price="500", unit="PLN/MWh")
    e = await setup(hass, freezer, config_entry)
    await tick(hass, freezer, "10:59:50")
    meters(hass, 100.0, 52.0, price="500", unit="PLN/MWh")
    await tick(hass, freezer, "11:59:50")
    assert value(hass, e["money_daily"]) == 1.0


async def test_unavailable_meter_spans_two_hours(hass, freezer, config_entry, caplog):
    meters(hass, 100.0, 50.0)
    e = await setup(hass, freezer, config_entry)
    await tick(hass, freezer, "10:59:50")
    meters(hass, 101.0, 52.0)
    await tick(hass, freezer, "11:59:50")

    hass.states.async_set(EXPORT, STATE_UNAVAILABLE)
    await tick(hass, freezer, "12:59:50")
    meters(hass, 105.0, 55.0)  # 12:00-14:00: +3 oddane, +4 pobrane
    await tick(hass, freezer, "13:59:50")

    assert value(hass, e["energy_hourly"]) == STATE_UNKNOWN
    assert value(hass, e["money_daily"]) == 0.5  # tylko godzina 11
    assert value(hass, e["energy_daily"]) == 1.0 - 1.0
    assert "więcej niż jedną godzinę" in caplog.text

    meters(hass, 105.0, 56.0)
    await tick(hass, freezer, "14:59:50")
    assert value(hass, e["energy_hourly"]) == 1.0


async def test_meter_reset_counts_zero(hass, freezer, config_entry, caplog):
    meters(hass, 1500.0, 50.0)
    e = await setup(hass, freezer, config_entry)
    await tick(hass, freezer, "10:59:50")
    meters(hass, 0.5, 51.0)
    await tick(hass, freezer, "11:59:50")
    assert value(hass, e["energy_hourly"]) == 1.0
    assert value(hass, e["energy_daily"]) == 1.0
    assert "zmalał" in caplog.text


async def test_midnight(hass, freezer, config_entry):
    meters(hass, 100.0, 50.0)
    e = await setup(hass, freezer, config_entry, start="22:30:00")
    await tick(hass, freezer, "22:59:50")
    meters(hass, 100.0, 52.0)
    await tick(hass, freezer, "23:59:50")
    assert value(hass, e["energy_daily"]) == 2.0
    assert value(hass, e["money_daily"]) == 1.0

    freezer.move_to(dt_util.parse_datetime("2026-03-11T00:00:00+01:00"))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert value(hass, e["energy_daily"]) == 0.0
    assert value(hass, e["money_daily"]) == 0.0

    # Okres 23:59:50-00:59:50 należy w całości do nowej doby (bez luki o północy).
    meters(hass, 100.0, 53.0)
    freezer.move_to(dt_util.parse_datetime("2026-03-11T00:59:50+01:00"))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert value(hass, e["energy_daily"]) == 1.0
    assert value(hass, e["energy_hourly"]) == 1.0


async def test_unload_stops_timers(hass, freezer, config_entry, caplog):
    meters(hass, 100.0, 50.0)
    e = await setup(hass, freezer, config_entry)
    await tick(hass, freezer, "10:59:50")
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    caplog.clear()
    caplog.set_level(logging.DEBUG)
    # Wyciekły timer próbowałby odczytać niedostępny licznik i zalogowałby to.
    hass.states.async_set(IMPORT, STATE_UNAVAILABLE)
    await tick(hass, freezer, "11:20:00")
    await tick(hass, freezer, "11:59:50")
    assert value(hass, e["energy_hourly"]) == STATE_UNAVAILABLE
    assert "brak poprawnej wartości" not in caplog.text


async def test_restore_baseline_after_restart(hass, freezer, config_entry):
    reg = er.async_get(hass)
    entity_id = reg.async_get_or_create(
        "sensor", DOMAIN, "test_entry_energy_daily", config_entry=config_entry,
        suggested_object_id="dzienny_bilans",
    ).entity_id
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, "2.0"),
                {
                    "value": 2.0,
                    "last_reset": at("00:00:00").isoformat(),
                    "baseline_import": 100.0,
                    "baseline_export": 50.0,
                    "baseline_time": at("10:59:50").isoformat(),
                    "baseline_sources": f"{IMPORT}|{EXPORT}",
                },
            )
        ],
    )
    meters(hass, 100.0, 50.0)
    await setup(hass, freezer, config_entry, start="11:30:00")
    assert value(hass, entity_id) == 2.0

    meters(hass, 100.0, 51.5)
    await tick(hass, freezer, "11:59:50")
    assert value(hass, entity_id) == 3.5


async def test_restore_from_previous_day_resets(hass, freezer, config_entry):
    reg = er.async_get(hass)
    entity_id = reg.async_get_or_create(
        "sensor", DOMAIN, "test_entry_money_daily", config_entry=config_entry,
        suggested_object_id="zarobek",
    ).entity_id
    old = State(entity_id, "7.0", last_updated=at("09:00:00").replace(day=9))
    mock_restore_cache(hass, [old])
    meters(hass, 100.0, 50.0)
    await setup(hass, freezer, config_entry)
    assert value(hass, entity_id) == 0.0


async def test_legacy_unique_ids_migrated(hass, freezer, config_entry):
    reg = er.async_get(hass)
    old = reg.async_get_or_create(
        "sensor", DOMAIN, f"rce_money_daily_{IMPORT}", config_entry=config_entry,
        suggested_object_id="dzienny_zarobek_rce",
    )
    meters(hass, 100.0, 50.0)
    await setup(hass, freezer, config_entry)
    migrated = reg.async_get(old.entity_id)
    assert migrated.unique_id == "test_entry_money_daily"
    assert hass.states.get("sensor.dzienny_zarobek_rce") is not None
