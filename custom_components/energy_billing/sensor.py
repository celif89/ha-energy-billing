import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_change

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Konfiguracja sensora na podstawie wpisu z interfejsu (Config Flow)."""
    import_sensor = config_entry.data.get("import_sensor")
    export_sensor = config_entry.data.get("export_sensor")
    price_sensor = config_entry.data.get("price_sensor")
    
    async_add_entities([EnergyBillingSensor(import_sensor, export_sensor, price_sensor)], True)

class EnergyBillingSensor(SensorEntity):
    """Encja obliczająca dzienny bilans finansowy."""
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:cash-register"
    _attr_native_unit_of_measurement = "PLN"
    _attr_device_class = "monetary"

    def __init__(self, import_sensor, export_sensor, price_sensor):
        self._import_sensor = import_sensor
        self._export_sensor = export_sensor
        self._price_sensor = price_sensor
        
        # Nazwa i unikalne ID (pozwala na zmianę ikony/nazwy w UI)
        self._attr_name = "Dzienny Zarobek RCE"
        self._attr_unique_id = f"rce_billing_{import_sensor.split('.')[-1]}"
        
        self._state = 0.0
        self.last_import = None
        self.last_export = None

    @property
    def native_value(self):
        """Zwraca aktualny stan zaokrąglony do 2 miejsc po przecinku."""
        return round(self._state, 2)

    async def async_added_to_hass(self):
        """Rejestracja zdarzeń po dodaniu sensora do systemu."""
        # Obliczaj o 59:50 każdej godziny
        async_track_time_change(self.hass, self._update_billing, minute=59, second=50)
        # Resetuj o północy
        async_track_time_change(self.hass, self._reset_daily, hour=0, minute=0, second=0)

    async def _update_billing(self, now):
        """Główna logika obliczeniowa wywoływana co godzinę."""
        try:
            st_import = self.hass.states.get(self._import_sensor)
            st_export = self.hass.states.get(self._export_sensor)
            st_price = self.hass.states.get(self._price_sensor)

            # Sprawdzenie czy wszystkie dane są dostępne
            if not (st_import and st_export and st_price):
                _LOGGER.warning("Brak dostępu do sensorów wejściowych")
                return

            # Pominięcie stanów niedostępnych
            if any(s.state in ['unknown', 'unavailable'] for s in [st_import, st_export, st_price]):
                return

            curr_import = float(st_import.state)
            curr_export = float(st_export.state)
            price = float(st_price.state)

            # Pierwsze uruchomienie po starcie HA tylko pobiera stany początkowe
            if self.last_import is not None and self.last_export is not None:
                diff_import = curr_import - self.last_import
                diff_export = curr_export - self.last_export
                
                # Bilans netto: (Pobór - Oddawanie) * Cena
                # Jeśli oddawanie jest większe, wynik będzie ujemny (zarobek)
                godzinny_wynik = (diff_import - diff_export) * price
                self._state += godzinny_wynik
                
                _LOGGER.info("Obliczono bilans godzinowy: %s PLN", round(godzinny_wynik, 4))
                self.async_write_ha_state()

            # Zapamiętanie stanów na kolejną godzinę
            self.last_import = curr_import
            self.last_export = curr_export

        except Exception as e:
            _LOGGER.error("Błąd podczas aktualizacji bilansu RCE: %s", e)

    async def _reset_daily(self, now):
        """Resetowanie licznika o północy."""
        self._state = 0.0
        _LOGGER.info("Zresetowano dzienny licznik zarobków RCE")
        self.async_write_ha_state()
