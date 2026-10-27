"""Scheepstypes uit de SDE: naam → type-id (voor het icoontje) en de klasse die erbij hoort.

Leest eve_sde (CorpTools) of anders eveuniverse; zonder een van beide valt alles terug op
een standaardschip per klasse.
"""

from django.utils import translation

from .models import SchipType

# SDE-groep → onze klasse. 4594 = Lancer Dreadnought.
GROEP_KLASSE = {
    902: SchipType.JF,
    547: SchipType.CARRIER,
    485: SchipType.DREAD,
    4594: SchipType.DREAD,
    1538: SchipType.FAX,
    659: SchipType.SUPER,
    30: SchipType.TITAN,
    883: SchipType.RORQUAL,
}


def _zoek(**filters) -> list[tuple[int, str, int]]:
    """(type_id, naam, groep_id) van gepubliceerde capitals die aan de filters voldoen."""
    # eve_sde vertaalt `name` via modeltranslation; in een Nederlandse sessie wordt dat
    # stilletjes `name_nl`, en die is leeg. Scheepsnamen zijn in elke taal hetzelfde.
    with translation.override("en"):
        try:
            from eve_sde.models import ItemType

            qs = ItemType.objects.filter(group_id__in=GROEP_KLASSE, published=True, **filters)
            return list(qs.order_by("name").values_list("id", "name", "group_id")[:15])
        except Exception:  # noqa: BLE001
            pass
        try:
            from eveuniverse.models import EveType

            qs = EveType.objects.filter(eve_group_id__in=GROEP_KLASSE, published=True, **filters)
            return list(qs.order_by("name").values_list("id", "name", "eve_group_id")[:15])
        except Exception:  # noqa: BLE001
            return []


def zoek_namen(q: str) -> list[str]:
    return [naam for _id, naam, _groep in _zoek(name__istartswith=q)]


def herken(naam: str) -> tuple[int | None, str | None]:
    """'nyx' → (23913, 'super'); onbekend → (None, None)."""
    if not naam.strip():
        return None, None
    rijen = _zoek(name__iexact=naam.strip())
    if not rijen:
        return None, None
    type_id, _naam, groep = rijen[0]
    return type_id, GROEP_KLASSE.get(groep)
