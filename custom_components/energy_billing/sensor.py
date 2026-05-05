from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_change

async def async_setup_entry(hass, config_entry, async_add_entities):
    # Pobieramy dane zapisane w okienkach
    import_sensor = config_entry.data.get("import_sensor")
    export_sensor = config_entry.data.get("export_sensor")
    price_sensor = config_entry.data.get("price_sensor")
    
    async_add_entities([EnergyBillingSensor(import_sensor, export_sensor, price_sensor)], True)

class EnergyBillingSensor(SensorEntity):
    def __init__(self, import_sensor, export_sensor, price_sensor):
        self._import_sensor = import_sensor
        self._export_sensor = export_sensor
        self._price_sensor = price_sensor
        self._attr_name = "Dzienny Zarobek RCE"
        self._attr_native_unit_of_measurement = "PLN"
        self._attr_unique_id = f"rce_billing_{import_sensor}"
        self._state = 0.0
        self.last_import = None
        self.last_export = None

    async def async_added_to_hass(self):
        async_track_time_change(self.hass, self._update_billing, minute=59, second=50)
        async_track_time_change(self.hass, self._reset_daily, hour=0, minute=0, second=0)

    async def _update_billing(self, now):
        st_import = self.hass.states.get(self._import_sensor)
        st_export = self.hass.states.get(self._export_sensor)
        st_price = self.hass.states.get(self._price_sensor)

        if st_import and st_export and st_price:
            curr_import = float(st_import.state)
            curr_export = float(st_export.state)
            price = float(st_price.state)

            if self.last_import is not None:
                diff_import = curr_import - self.last_import
                diff_export = curr_export - self.last_export
                self._state += ((diff_import - diff_export) * price)
                self.async_write_ha_state()

            self.last_import = curr_import
            self.last_export = curr_export

    async def _reset_daily(self, now):
        self._state = 0.0
        self.async_write_ha_state()
