# Meeliften

Een ruimte-beurs voor [Alliance Auth](https://gitlab.com/allianceauth/allianceauth).
Capital-piloten (Jump Freighter, carrier, dread, FAX, super, titan, Rorqual) melden welk schip
ze hebben en hoeveel ruimte ze over hebben. Leden zonder capital vragen daarin een plekje, of zetten zelf
een vraag op het bord (hoeveel m³, plus een opmerking zoals "Ishtar + ammo, Jita naar Q-02UL") die een
piloot kan oppakken.

Alles wordt door de leden zelf ingevuld; er zijn geen ESI-scopes nodig.

## Zo werkt het

- **Ruimte aanbieden**: kies het schip uit de lijst (alle capitals, met icoontje), vrije m³ en/of vrije SMB-plekken.
- **Plekje vragen** bij een piloot (m³ en/of een opmerking): de piloot krijgt een AA-melding en accepteert of weigert.
  Geweigerd? Dan staat de vraag los op het bord voor een andere piloot.
- **Vervoer zoeken** zonder rit: een piloot klikt *Ik neem het mee*.
- Bij elke rit zie je hoeveel ruimte er **nog vrij** is (aangeboden min wat al is toegezegd).
- Afgeleverd / ingetrokken / rit geannuleerd: de ander krijgt steeds een melding.
- Aangeboden ruimte en losse vragen verdwijnen na 30 dagen (of eerder als ze worden afgesloten).

## Installatie

```bash
pip install git+https://github.com/jweijdert-eng/aa-meeliften.git
```

Zet `'meeliften'` in `INSTALLED_APPS` (in `local.py`) en draai daarna:

```bash
python manage.py migrate meeliften
python manage.py collectstatic --noinput
```

Herstart daarna de webserver en Celery.

## Permissies

| Permissie | Wat |
|---|---|
| `meeliften.basic_access` | Het bord gebruiken: ritten aanbieden, plekjes vragen, vervoer zoeken |
| `meeliften.manage` | Ritten en vragen van anderen bewerken, annuleren of afhandelen |

Geef `basic_access` aan de state *Member* (of de groep die het moet zien).
