# Licznik Energii RCE

Niestandardowa integracja Home Assistant do rozliczania energii w net-billingu
godzinowym według ceny RCE.

## Encje

| Encja | Opis |
|---|---|
| Dzienny zarobek (PLN) | Suma po godzinach: dodatni bilans godziny × cena RCE. Zerowana o północy. |
| Miesięczny zarobek (PLN) | Jak dzienny zarobek, ale sumowany przez cały miesiąc. Zerowany 1. dnia miesiąca o północy. |
| Godzinowy bilans energii (kWh) | Energia oddana − pobrana w ostatnim okresie rozliczeniowym. |
| Dzienny bilans energii (kWh) | Suma bilansów godzinowych z doby. Zerowana o północy. |
| Bieżący bilans godzinowy (kWh) | Bilans trwającego okresu, odświeżany co 2 minuty. |

Okres rozliczeniowy kończy się o **xx:59:50** każdej godziny. Wszystkie encje
mają `state_class: total` z `last_reset`, więc trafiają do statystyk
długoterminowych.

## Konfiguracja

Ustawienia → Urządzenia i usługi → Dodaj integrację → *Licznik Energii RCE*:

- **Licznik poboru / oddania** – narastające liczniki energii w kWh,
- **Sensor ceny** – cena RCE w PLN/kWh (np. `0,50`); jeśli jednostką sensora
  jest PLN/MWh, cena jest automatycznie dzielona przez 1000.

Sensory można później zmienić w opcjach integracji (*Konfiguruj*).

## Zachowanie w sytuacjach brzegowych

- **Restart HA** – odczyty bazowe są zapamiętywane, więc godzina z restartem
  jest rozliczana normalnie (o ile HA działa w chwili rozliczenia xx:59:50).
- **Licznik niedostępny w chwili rozliczenia** – następny okres obejmuje dwie
  godziny. Bilans dzienny je uwzględnia (bilans jest addytywny), bilans
  godzinowy ma stan `unknown`, a zarobek pomija ten okres, bo nie da się go
  rozdzielić na godziny. W logu pojawia się ostrzeżenie.
- **Spadek licznika** (wymiana/zerowanie) – przyrost jest liczony jako 0,
  z ostrzeżeniem w logu.

## Testy

```bash
pip install -r requirements_test.txt
pytest
```
