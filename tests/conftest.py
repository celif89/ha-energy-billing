"""Wspólne fixture'y testów."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.energy_billing.const import (
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    CONF_PRICE_SENSOR,
    DOMAIN,
)

IMPORT = "sensor.grid_import"
EXPORT = "sensor.grid_export"
PRICE = "sensor.rce_price"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def warsaw(hass):
    await hass.config.async_set_time_zone("Europe/Warsaw")


@pytest.fixture
def config_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mój Licznik RCE",
        data={
            CONF_IMPORT_SENSOR: IMPORT,
            CONF_EXPORT_SENSOR: EXPORT,
            CONF_PRICE_SENSOR: PRICE,
        },
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)
    return entry
