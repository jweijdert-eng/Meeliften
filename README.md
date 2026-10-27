# Meeliften

Een ruimte-beurs voor [Alliance Auth](https://gitlab.com/allianceauth/allianceauth).
Capital-piloten (Jump Freighter, carrier, dread, FAX, super, titan, Rorqual) melden een rit
met de ruimte die ze over hebben. Leden zonder capital vragen daarin een plekje, of zetten zelf
een vraag op het bord ("Jita → 1DQ1-A, 40.000 m³ + 1 Ishtar") die een piloot kan oppakken.

Alles wordt door de leden zelf ingevuld; er zijn geen ESI-scopes nodig.

## Zo werkt het

- **Rit aanbieden**: schip, van → naar, vertrek (EVE-tijd), vrije m³ en/of vrije SMB-plekken.
- **Plekje vragen** bij een rit: de piloot krijgt een AA-melding en accepteert of weigert.
  Geweigerd? Dan staat de vraag los op het bord voor een andere piloot.
- **Vervoer zoeken** zonder rit: een piloot klikt *Ik neem het mee*.
- Bij elke rit zie je hoeveel ruimte er **nog vrij** is (aangeboden min wat al is toegezegd).
- Afgeleverd / ingetrokken / rit geannuleerd: de ander krijgt steeds een melding.
- Ritten verdwijnen een dag na vertrek (zonder vertrektijd na 14 dagen); losse vragen na hun
  "uiterlijk"-datum (zonder datum na 30 dagen).

Systeemnamen worden aangevuld uit `eve_sde` (CorpTools) of `eveuniverse`, als een van beide
geïnstalleerd is. Zonder die twee typ je de naam gewoon zelf.

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
