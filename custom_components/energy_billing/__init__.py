"""Integracja Licznik Energii RCE."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_IMPORT_SENSOR, LEGACY_UNIQUE_ID_PREFIXES

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await _async_migrate_unique_ids(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Przeładuj integrację po zmianie opcji (innych sensorów)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Zamień unique_id z wersji <= 1.5.0 (oparte o sensor poboru) na oparte o wpis.

    entity_id i historia encji pozostają bez zmian.
    """
    import_sensor = entry.data.get(CONF_IMPORT_SENSOR)

    @callback
    def _migrate(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        for prefix, key in LEGACY_UNIQUE_ID_PREFIXES.items():
            if entity_entry.unique_id == f"{prefix}{import_sensor}":
                return {"new_unique_id": f"{entry.entry_id}_{key}"}
        return None

    await er.async_migrate_entries(hass, entry.entry_id, _migrate)
