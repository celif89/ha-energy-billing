"""Sensory rozliczenia energii w net-billingu godzinowym (cena RCE)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfEnergy
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from .calc import hourly_revenue, meter_delta, parse_number, price_per_kwh
from .const import (
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    CONF_PRICE_SENSOR,
    DOMAIN,
    KEY_ENERGY_DAILY,
    KEY_ENERGY_HOURLY,
    KEY_HOUR_PROGRESS,
    KEY_MONEY_DAILY,
    MAX_SETTLEMENT_PERIOD,
    SETTLEMENT_MINUTE,
    SETTLEMENT_SECOND,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config = {**entry.data, **entry.options}
    async_add_entities(
        [
            EnergyDailyMoneySensor(entry, config),
            EnergyHourlyBalanceSensor(entry, config),
            EnergyDailyBalanceSensor(entry, config),
            EnergyCurrentHourProgressSensor(entry, config),
        ]
    )


@dataclass
class Baseline:
    """Odczyty liczników na początku bieżącego okresu rozliczeniowego."""

    imported: float
    exported: float
    time: datetime
    sources: str


@dataclass
class Period:
    """Zamknięty okres rozliczeniowy (od poprzedniego do bieżącego rozliczenia)."""

    imported: float
    exported: float
    start: datetime
    end: datetime

    @property
    def balance(self) -> float:
        return self.exported - self.imported

    @property
    def is_single_hour(self) -> bool:
        return self.end - self.start <= MAX_SETTLEMENT_PERIOD


def _parse_dt(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


@dataclass
class BillingExtraData(ExtraStoredData):
    """Dane zapisywane między restartami HA (wartość, last_reset, odczyty bazowe)."""

    value: float | None
    last_reset: datetime | None
    baseline: Baseline | None

    def as_dict(self) -> dict[str, Any]:
        baseline = self.baseline
        return {
            "value": self.value,
            "last_reset": self.last_reset.isoformat() if self.last_reset else None,
            "baseline_import": baseline.imported if baseline else None,
            "baseline_export": baseline.exported if baseline else None,
            "baseline_time": baseline.time.isoformat() if baseline else None,
            "baseline_sources": baseline.sources if baseline else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BillingExtraData | None:
        try:
            baseline = None
            baseline_time = _parse_dt(data["baseline_time"])
            if baseline_time is not None:
                baseline = Baseline(
                    float(data["baseline_import"]),
                    float(data["baseline_export"]),
                    baseline_time,
                    str(data["baseline_sources"]),
                )
            value = data["value"]
            return cls(
                None if value is None else float(value),
                _parse_dt(data["last_reset"]),
                baseline,
            )
        except (KeyError, TypeError, ValueError):
            return None


class EnergyBillingSensor(RestoreEntity, SensorEntity):
    """Wspólna logika: rozliczenie co godzinę o xx:59:50 względem odczytów bazowych."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.TOTAL
    _key: str

    def __init__(self, entry: ConfigEntry, config: dict[str, Any]) -> None:
        self._import_sensor: str = config[CONF_IMPORT_SENSOR]
        self._export_sensor: str = config[CONF_EXPORT_SENSOR]
        self._sources = f"{self._import_sensor}|{self._export_sensor}"
        self._value: float | None = 0.0
        self._baseline: Baseline | None = None
        self._attr_last_reset = None
        self._attr_unique_id = f"{entry.entry_id}_{self._key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | None:
        return None if self._value is None else round(self._value, 4)

    @property
    def extra_restore_state_data(self) -> BillingExtraData:
        return BillingExtraData(self._value, self._attr_last_reset, self._baseline)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_restore()
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._handle_settlement,
                minute=SETTLEMENT_MINUTE,
                second=SETTLEMENT_SECOND,
            )
        )

    async def _async_restore(self) -> None:
        extra = await self.async_get_last_extra_data()
        data = BillingExtraData.from_dict(extra.as_dict()) if extra else None
        if data is not None:
            self._value = data.value
            self._attr_last_reset = data.last_reset
            # Odczyty bazowe innych liczników (zmiana w opcjach) są bezużyteczne.
            if data.baseline is not None and data.baseline.sources == self._sources:
                self._baseline = data.baseline
        elif (state := await self.async_get_last_state()) is not None:
            # Wersja <= 1.5.0 zapisywała tylko wartość stanu.
            self._restore_legacy(state)

    def _restore_legacy(self, state: State) -> None:
        self._value = parse_number(state.state)

    def _read(self, entity_id: str, level: int = logging.WARNING) -> float | None:
        state = self.hass.states.get(entity_id)
        value = parse_number(state.state) if state else None
        if value is None:
            _LOGGER.log(
                level,
                "%s: brak poprawnej wartości z %s (stan: %s)",
                self.entity_id,
                entity_id,
                state.state if state else "encja nie istnieje",
            )
        return value

    def _read_meters(self, level: int = logging.WARNING) -> tuple[float, float] | None:
        imported = self._read(self._import_sensor, level)
        exported = self._read(self._export_sensor, level)
        if imported is None or exported is None:
            return None
        return imported, exported

    def _delta(self, entity_id: str, current: float, previous: float) -> float:
        if current < previous:
            _LOGGER.warning(
                "%s: licznik %s zmalał z %s do %s (wymiana lub zerowanie licznika?) "
                "- przyjmuję przyrost 0",
                self.entity_id,
                entity_id,
                previous,
                current,
            )
        return meter_delta(current, previous)

    @callback
    def _handle_settlement(self, now: datetime) -> None:
        readings = self._read_meters()
        if readings is None:
            # Odczyty bazowe zostają; następne rozliczenie obejmie dłuższy okres.
            return
        imported, exported = readings
        end = dt_util.utcnow()
        previous = self._baseline
        self._baseline = Baseline(imported, exported, end, self._sources)
        period = None
        if previous is not None:
            period = Period(
                imported=self._delta(self._import_sensor, imported, previous.imported),
                exported=self._delta(self._export_sensor, exported, previous.exported),
                start=previous.time,
                end=end,
            )
            if not period.is_single_hour:
                _LOGGER.warning(
                    "%s: okres rozliczeniowy %s - %s obejmuje więcej niż jedną godzinę "
                    "(brak odczytu lub HA wyłączony w chwili rozliczenia)",
                    self.entity_id,
                    dt_util.as_local(period.start),
                    dt_util.as_local(period.end),
                )
        self._settle(period)
        self.async_write_ha_state()

    def _settle(self, period: Period | None) -> None:
        """Uwzględnij zamknięty okres; None oznacza pierwszy odczyt bazowy."""
        raise NotImplementedError


class DailyBillingSensor(EnergyBillingSensor):
    """Sensor sumujący godziny w ramach doby, zerowany o północy."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._value is None:
            self._value = 0.0
        self._roll_day()
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._handle_midnight, hour=0, minute=0, second=0
            )
        )

    def _restore_legacy(self, state: State) -> None:
        super()._restore_legacy(state)
        self._attr_last_reset = dt_util.start_of_local_day(
            dt_util.as_local(state.last_updated)
        )

    def _roll_day(self) -> bool:
        start = dt_util.start_of_local_day()
        if self._attr_last_reset is None or self._attr_last_reset < start:
            self._value = 0.0
            self._attr_last_reset = start
            return True
        return False

    @callback
    def _handle_midnight(self, now: datetime) -> None:
        if self._roll_day():
            self.async_write_ha_state()

    def _settle(self, period: Period | None) -> None:
        self._roll_day()
        if period is None:
            return
        if not period.is_single_hour and period.start < self._attr_last_reset:
            _LOGGER.warning(
                "%s: pominięto okres obejmujący północ - nie da się go przypisać do doby",
                self.entity_id,
            )
            return
        self._add_period(period)

    def _add_period(self, period: Period) -> None:
        raise NotImplementedError


class EnergyDailyMoneySensor(DailyBillingSensor):
    _key = KEY_MONEY_DAILY
    _attr_name = "Dzienny zarobek"
    _attr_native_unit_of_measurement = "PLN"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:cash-plus"

    def __init__(self, entry: ConfigEntry, config: dict[str, Any]) -> None:
        super().__init__(entry, config)
        self._price_sensor: str = config[CONF_PRICE_SENSOR]

    def _read_price(self) -> float | None:
        price = self._read(self._price_sensor)
        if price is None:
            return None
        unit = self.hass.states.get(self._price_sensor).attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        )
        return price_per_kwh(price, unit)

    def _add_period(self, period: Period) -> None:
        if not period.is_single_hour:
            # Saldo jest liczone osobno dla każdej godziny - sumy kilku godzin nie
            # da się rozdzielić, więc ten okres nie jest wyceniany.
            _LOGGER.warning("%s: okres dłuższy niż godzina nie został wyceniony", self.entity_id)
            return
        price = self._read_price()
        if price is None:
            _LOGGER.warning("%s: brak ceny - godzina nie została wyceniona", self.entity_id)
            return
        self._value += hourly_revenue(period.exported, period.imported, price)


class EnergyDailyBalanceSensor(DailyBillingSensor):
    _key = KEY_ENERGY_DAILY
    _attr_name = "Dzienny bilans energii"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_suggested_display_precision = 3
    _attr_icon = "mdi:scale-balance"

    def _add_period(self, period: Period) -> None:
        # Bilans jest addytywny, więc dłuższy okres w obrębie doby też jest poprawny.
        self._value += period.balance


class EnergyHourlyBalanceSensor(EnergyBillingSensor):
    _key = KEY_ENERGY_HOURLY
    _attr_name = "Godzinowy bilans energii"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_suggested_display_precision = 3
    _attr_icon = "mdi:clock-outline"

    def _settle(self, period: Period | None) -> None:
        if period is None:
            return
        self._attr_last_reset = period.start
        self._value = period.balance if period.is_single_hour else None


class EnergyCurrentHourProgressSensor(EnergyBillingSensor):
    """Bilans bieżącego okresu rozliczeniowego, odświeżany co 2 minuty."""

    _key = KEY_HOUR_PROGRESS
    _attr_name = "Bieżący bilans godzinowy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_suggested_display_precision = 3
    _attr_icon = "mdi:progress-clock"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._handle_progress, minute="/2", second=0
            )
        )

    def _settle(self, period: Period | None) -> None:
        # Nowy okres rozliczeniowy zaczyna się dokładnie w chwili rozliczenia.
        self._value = 0.0
        self._attr_last_reset = self._baseline.time

    @callback
    def _handle_progress(self, now: datetime) -> None:
        baseline = self._baseline
        if baseline is None:
            return
        if dt_util.utcnow() - baseline.time > MAX_SETTLEMENT_PERIOD:
            # Ominięte rozliczenie - bilans "bieżącej godziny" byłby błędny.
            if self._value is not None:
                self._value = None
                self.async_write_ha_state()
            return
        readings = self._read_meters(logging.DEBUG)
        if readings is None:
            return
        imported, exported = readings
        self._value = meter_delta(exported, baseline.exported) - meter_delta(
            imported, baseline.imported
        )
        self.async_write_ha_state()
