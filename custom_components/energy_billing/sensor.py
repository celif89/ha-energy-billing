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
        EnergyBillingSensor(import_sensor, export_sensor, price_sensor),
        EnergyBalanceSensor(import_sensor, export_sensor)
    ], True)

class EnergyBillingBase(RestoreEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, import_sensor, export_sensor):
        self._import_sensor = import_sensor
        self._export_sensor = export_sensor
        self._state = 0.0
        self.last_import = None
        self.last_export = None

    async def async_added_to_hass(self):
        """Przywracanie stanu i ustawienie harmonogramu."""
        await super().async_added_to_hass()
        
        old_state = await self.async_get_last_state()
        if old_state is not None and old_state.state not in ['unknown', 'unavailable']:
            try:
                self._state = float(old_state.state)
            except ValueError:
                self._state = 0.0

        # POWRÓT: Obliczamy tylko raz na godzinę (59:50)
        async_track_time_change(self.hass, self._update_values, minute=59, second=50)
        
        # Reset o północy
        async_track_time_change(self.hass, self._reset_daily, hour=0, minute=0, second=0)

    async def _reset_daily(self, now):
        self._state = 0.0
        self.async_write_ha_state()

class EnergyBillingSensor(EnergyBillingBase):
    _attr_native_unit_of_measurement = "PLN"
    _attr_device_class = "monetary"
    _attr_icon = "mdi:cash-plus"

    def __init__(self, import_sensor, export_sensor, price_sensor):
        super().__init__(import_sensor, export_sensor)
        self._price_sensor = price_sensor
        self._attr_name = "Dzienny Zarobek RCE"
        self._attr_unique_id = f"rce_money_{import_sensor.split('.')[-1]}"

    @property
    def native_value(self):
        return round(self._state, 2)

    async def _update_values(self, now):
        st_import = self.hass.states.get(self._import_sensor)
        st_export = self.hass.states.get(self._export_sensor)
        st_price = self.hass.states.get(self._price_sensor)

        if st_import and st_export and st_price:
            try:
                curr_import = float(st_import.state)
                curr_export = float(st_export.state)
                price = float(st_price.state)

                if self.last_import is not None:
                    diff_import = curr_import - self.last_import
                    diff_export = curr_export - self.last_export
                    # Zarobek: (Eksport - Import) * Cena
                    self._state += ((diff_export - diff_import) * price)
                    self.async_write_ha_state()

                self.last_import = curr_import
                self.last_export = curr_export
            except (ValueError, TypeError):
                _LOGGER.warning("Błąd wartości sensora")

class EnergyBalanceSensor(EnergyBillingBase):
    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = "energy"
    _attr_icon = "mdi:scale-balance"

    def __init__(self, import_sensor, export_sensor):
        super().__init__(import_sensor, export_sensor)
        self._attr_name = "Dzienny Bilans Energii RCE"
        self._attr_unique_id = f"rce_energy_bal_{import_sensor.split('.')[-1]}"

    @property
    def native_value(self):
        return round(self._state, 3)

    async def _update_values(self, now):
        st_import = self.hass.states.get(self._import_sensor)
        st_export = self.hass.states.get(self._export_sensor)

        if st_import and st_export:
            try:
                curr_import = float(st_import.state)
                curr_export = float(st_export.state)

                if self.last_import is not None:
                    diff_import = curr_import - self.last_import
                    diff_export = curr_export - self.last_export
                    self._state += (diff_export - diff_import)
                    self.async_write_ha_state()

                self.last_import = curr_import
                self.last_export = curr_export
            except (ValueError, TypeError):
                pass
