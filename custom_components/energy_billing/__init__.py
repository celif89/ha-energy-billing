async def async_setup_entry(hass, entry):
    # Dodaliśmy literkę 's' w setups oraz nawiasy [] wokół "sensor"
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass, entry):
    # To pozwoli na poprawne usunięcie integracji bez restartu
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
