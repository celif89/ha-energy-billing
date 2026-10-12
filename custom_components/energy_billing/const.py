"""Stałe integracji Licznik Energii RCE."""
from datetime import timedelta

DOMAIN = "energy_billing"

CONF_IMPORT_SENSOR = "import_sensor"
CONF_EXPORT_SENSOR = "export_sensor"
CONF_PRICE_SENSOR = "price_sensor"

DEFAULT_TITLE = "Mój Licznik RCE"

# Moment rozliczenia okresu godzinowego (xx:59:50).
SETTLEMENT_MINUTE = 59
SETTLEMENT_SECOND = 50

# Okres dłuższy niż ten próg obejmuje więcej niż jedną godzinę rozliczeniową
# (np. licznik był niedostępny albo HA był wyłączony w chwili rozliczenia).
MAX_SETTLEMENT_PERIOD = timedelta(minutes=70)

# Klucze encji (część unique_id) i prefiksy unique_id z wersji <= 1.5.0.
KEY_MONEY_DAILY = "money_daily"
KEY_MONEY_MONTHLY = "money_monthly"
KEY_ENERGY_HOURLY = "energy_hourly"
KEY_ENERGY_DAILY = "energy_daily"
KEY_HOUR_PROGRESS = "hour_progress"

LEGACY_UNIQUE_ID_PREFIXES = {
    "rce_money_daily_": KEY_MONEY_DAILY,
    "rce_energy_hourly_": KEY_ENERGY_HOURLY,
    "rce_energy_daily_": KEY_ENERGY_DAILY,
    "rce_hour_progress_": KEY_HOUR_PROGRESS,
}
