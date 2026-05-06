import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_track_time_change

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    import_sensor = config_entry.data.get("import_sensor")
    export_sensor = config_entry.data.get("export_sensor")
    price_sensor = config_entry.data.get("price_sensor")
    
    async_add_entities([
        EnergyDailyMoneySensor(import_sensor, export_sensor, price_sensor),
        EnergyHourlyBalanceSensor(import_sensor, export_sensor),
        EnergyDailyBalanceSensor(import_sensor, export_sensor)
    ], True)

class EnergyBase(RestoreEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, import_sensor, export_sensor):
        self._import_sensor = import_sensor
        self._export_sensor = export_sensor
        self._state = 0.0
        self.last_import = None
        self.last_export = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if old_state is not None and old_state.state not in ['unknown', 'unavailable']:
            try: self._state = float(old_state.state)
            except ValueError: self._state = 0.0
        async_track_time_change(self.hass, self._update_values, minute=59, second=50)

    @property
    def native_value(self): return round(self._state, 3)

class EnergyDailyMoneySensor(EnergyBase):
    """Suma PLN od północy."""
    _attr_native_unit_of_measurement = "PLN"
    _attr_device_class = "monetary"
    _attr_icon = "mdi:cash-plus"
    def __init__(self, import_sensor, export_sensor, price_sensor):
        super().__init__(import_sensor, export_sensor)
        self._price_sensor = price_sensor
        self._attr_name = "Dzienny Zarobek RCE"
        self._attr_unique_id = f"rce_money_daily_{import_sensor}"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        async_track_time_change(self.hass, self._reset_daily, hour=0, minute=0, second=0)

    async def _reset_daily(self, now):
        self._state = 0.0
        self.async_write_ha_state()

    async def _update_values(self, now):
        st_i = self.hass.states.get(self._import_sensor)
        st_e = self.hass.states.get(self._export_sensor)
        st_p = self.hass.states.get(self._price_sensor)
        if st_i and st_e and st_p:
            curr_i, curr_e, p = float(st_i.state), float(st_e.state), float(st_p.state)
            if self.last_import is not None:
                self._state += ((curr_e - self.last_export) - (curr_i - self.last_import)) * p
                self.async_write_ha_state()
            self.last_import, self.last_export = curr_i, curr_e

class EnergyHourlyBalanceSensor(EnergyBase):
    """Bilans tylko z ostatniej godziny (nie sumuje)."""
    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = "energy"
    _attr_icon = "mdi:clock-outline"
    def __init__(self, import_sensor, export_sensor):
        super().__init__(import_sensor, export_sensor)
        self._attr_name = "Godzinowy Bilans Energii RCE"
        self._attr_unique_id = f"rce_energy_hourly_{import_sensor}"

    async def _update_values(self, now):
        st_i = self.hass.states.get(self._import_sensor)
        st_e = self.hass.states.get(self._export_sensor)
        if st_i and st_e:
            curr_i, curr_e = float(st_i.state), float(st_e.state)
            if self.last_import is not None:
                # TUTAJ: Nie używamy +=, więc pokazuje tylko ostatnią godzinę
                self._state = (curr_e - self.last_export) - (curr_i - self.last_import)
                self.async_write_ha_state()
            self.last_import, self.last_export = curr_i, curr_e

class EnergyDailyBalanceSensor(EnergyBase):
    """Suma kWh od północy."""
    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = "energy"
    _attr_icon = "mdi:scale-balance"
    def __init__(self, import_sensor, export_sensor):
        super().__init__(import_sensor, export_sensor)
        self._attr_name = "Dzienny Bilans Energii RCE"
        self._attr_unique_id = f"rce_energy_daily_{import_sensor}"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        async_track_time_change(self.hass, self._reset_daily, hour=0, minute=0, second=0)

    async def _reset_daily(self, now):
        self._state = 0.0
        self.async_write_ha_state()

    async def _update_values(self, now):
        st_i = self.hass.states.get(self._import_sensor)
        st_e = self.hass.states.get(self._export_sensor)
        if st_i and st_e:
            curr_i, curr_e = float(st_i.state), float(st_e.state)
            if self.last_import is not None:
                self._state += (curr_e - self.last_export) - (curr_i - self.last_import)
                self.async_write_ha_state()
            self.last_import, self.last_export = curr_i, curr_e
