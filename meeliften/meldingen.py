"""AA-notificaties voor Meeliften — elke stap in een aanvraag laat de ander het weten."""

from allianceauth.notifications.models import Notification


def naam(user) -> str:
    main = getattr(getattr(user, "profile", None), "main_character", None)
    return main.character_name if main else user.username


def _stuur(user, titel: str, tekst: str, level=Notification.Level.INFO) -> None:
    if user:
        Notification.objects.notify_user(user=user, title=titel, message=tekst, level=level)


def plekje_gevraagd(vraag) -> None:
    rit = vraag.rit
    _stuur(rit.piloot, "Meeliften: iemand wil mee",
           f"{naam(vraag.aanvrager)} wil mee met je {rit}: {vraag.omschrijving}. Zeg ja of nee op de Meeliften-pagina.")


def geaccepteerd(vraag) -> None:
    _stuur(vraag.aanvrager, "Meeliften: je mag mee",
           f"{naam(vraag.vervoerder)} neemt '{vraag.omschrijving}' mee. "
           "Spreek in-game af hoe je het overdraagt.", Notification.Level.SUCCESS)


def geweigerd(vraag, rit) -> None:
    _stuur(vraag.aanvrager, "Meeliften: geen plek",
           f"{naam(rit.piloot)} kan '{vraag.omschrijving}' niet meenemen met {rit}. "
           "Probeer een andere piloot op de Meeliften-pagina.",
           Notification.Level.WARNING)


def teruggetrokken(vraag, vervoerder) -> None:
    _stuur(vraag.aanvrager, "Meeliften: vervoer vervalt",
           f"{naam(vervoerder)} kan '{vraag.omschrijving}' toch niet meenemen. "
           "Probeer een andere piloot op de Meeliften-pagina.",
           Notification.Level.WARNING)


def geannuleerd_door_aanvrager(vraag, vervoerder) -> None:
    _stuur(vervoerder, "Meeliften: verzoek ingetrokken",
           f"{naam(vraag.aanvrager)} heeft '{vraag.omschrijving}' ingetrokken; die ruimte is weer vrij.")


def afgeleverd(vraag, door) -> None:
    ander = vraag.aanvrager if door == vraag.vervoerder else vraag.vervoerder
    _stuur(ander, "Meeliften: afgeleverd",
           f"'{vraag.omschrijving}' is als afgeleverd gemarkeerd door {naam(door)}.",
           Notification.Level.SUCCESS)
