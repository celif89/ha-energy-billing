import logging
from datetime import timedelta
from homeassistant.helpers.event import async_track_time_change
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy, CURRENCY_EURO # Zmienimy na PLN w stanie

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([EnergyBillingSensor()], True)

class EnergyBillingSensor(SensorEntity):
    def __init__(self):
        self._attr_name = "Dzienny Zarobek RCE"
        self._attr_native_unit_of_measurement = "PLN"
        self._attr_unique_id = "energy_billing_rce_daily"
        self._state = 0.0
        # Przechowujemy stany z poprzedniej godziny do obliczenia bilansu
        self.last_import = None
        self.last_export = None

    @property
    def state(self):
        return round(self._state, 2)

    async def async_added_to_hass(self):
        # Wyzwalacz: 59 minuta i 50 sekunda każdej godziny
        async_track_time_change(self.hass, self._update_billing, minute=59, second=50)
        # Wyzwalacz: Północ (resetowanie licznika)
        async_track_time_change(self.hass, self._reset_daily, hour=0, minute=0, second=0)

    async def _update_billing(self, now):
        try:
            # Pobieramy aktualne stany liczników FoxESS
            current_import = float(self.hass.states.get("sensor.foxess_grid_consumption").state)
            current_export = float(self.hass.states.get("sensor.foxess_feedin").state)
            cena = float(self.hass.states.get("sensor.rce_pse_cena_sprzedazy_prosument").state)

            if self.last_import is not None and self.last_export is not None:
                # Obliczamy ile przybyło w ciągu ostatniej godziny
                diff_import = current_import - self.last_import
                diff_export = current_export - self.last_export
                
                # Bilans netto godziny
                bilans_godzinowy = diff_import - diff_export
                
                # Dodajemy do sumy dobowej (Bilans * Cena)
                self._state += (bilans_godzinowy * cena)
                self.async_write_ha_state()

            # Zapamiętujemy stany na następną godzinę
            self.last_import = current_import
            self.last_export = current_export

        except Exception as e:
            _LOGGER.error("Błąd przy obliczaniu bilansu energii: %s", e)

    async def _reset_daily(self, now):
        self._state = 0.0
        self.async_write_ha_state()
