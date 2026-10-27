"""AA-notificaties voor Meeliften — elke stap in een aanvraag laat de ander het weten."""

from allianceauth.notifications.models import Notification


def _naam(user) -> str:
    main = getattr(getattr(user, "profile", None), "main_character", None)
    return main.character_name if main else user.username


def _stuur(user, titel: str, tekst: str, level=Notification.Level.INFO) -> None:
    if user:
        Notification.objects.notify_user(user=user, title=titel, message=tekst, level=level)


def plekje_gevraagd(vraag) -> None:
    rit = vraag.rit
    _stuur(rit.piloot, "Meeliften: plekje gevraagd",
           f"{_naam(vraag.aanvrager)} wil mee met je {rit}: {vraag.wat} ({vraag.van} → {vraag.naar}). Accepteer of weiger op de Meeliften-pagina.")


def geaccepteerd(vraag) -> None:
    _stuur(vraag.aanvrager, "Meeliften: je kunt mee",
           f"{_naam(vraag.vervoerder)} neemt '{vraag.wat}' mee van {vraag.van} naar {vraag.naar}. "
           "Spreek in-game af hoe je het overdraagt.", Notification.Level.SUCCESS)


def geweigerd(vraag, rit) -> None:
    _stuur(vraag.aanvrager, "Meeliften: geen plek",
           f"{_naam(rit.piloot)} kan '{vraag.wat}' niet meenemen met {rit}. "
           "Je vraag staat nu los op het bord, zodat een andere piloot hem kan oppakken.",
           Notification.Level.WARNING)


def teruggetrokken(vraag, vervoerder) -> None:
    _stuur(vraag.aanvrager, "Meeliften: vervoer vervalt",
           f"{_naam(vervoerder)} kan '{vraag.wat}' toch niet meenemen. Je vraag staat weer open op het bord.",
           Notification.Level.WARNING)


def geannuleerd_door_aanvrager(vraag, vervoerder) -> None:
    _stuur(vervoerder, "Meeliften: aanvraag ingetrokken",
           f"{_naam(vraag.aanvrager)} heeft '{vraag.wat}' ingetrokken; die ruimte is weer vrij.")


def afgeleverd(vraag, door) -> None:
    ander = vraag.aanvrager if door == vraag.vervoerder else vraag.vervoerder
    _stuur(ander, "Meeliften: afgeleverd",
           f"'{vraag.wat}' ({vraag.van} → {vraag.naar}) is als afgeleverd gemarkeerd door {_naam(door)}.",
           Notification.Level.SUCCESS)
