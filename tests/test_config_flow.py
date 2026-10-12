from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.energy_billing.const import (
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    CONF_PRICE_SENSOR,
    DOMAIN,
)

from .conftest import EXPORT, IMPORT, PRICE

INPUT = {CONF_IMPORT_SENSOR: IMPORT, CONF_EXPORT_SENSOR: EXPORT, CONF_PRICE_SENSOR: PRICE}


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_create_entry(hass):
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == INPUT


async def test_same_sensor_error(hass):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**INPUT, CONF_EXPORT_SENSOR: IMPORT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_sensor"}


async def test_duplicate_aborts(hass, config_entry):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_changes_sensors(hass, config_entry):
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    new = {**INPUT, CONF_PRICE_SENSOR: "sensor.other_price"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], new)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.options[CONF_PRICE_SENSOR] == "sensor.other_price"
    assert config_entry.state is config_entries.ConfigEntryState.LOADED
