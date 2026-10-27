"""Kleine weergave-hulpjes voor Meeliften."""

from django import template

register = template.Library()


@register.filter
def m3(waarde) -> str:
    """280000 → '280.000'."""
    if waarde in (None, ""):
        return "–"
    return f"{int(waarde):,}".replace(",", ".")


@register.filter
def naam(user) -> str:
    main = getattr(getattr(user, "profile", None), "main_character", None)
    return main.character_name if main else getattr(user, "username", "?")


@register.filter
def portret(obj) -> str:
    """Portret van een EveCharacter, of van de main van een user."""
    char = obj if hasattr(obj, "portrait_url") else getattr(getattr(obj, "profile", None), "main_character", None)
    return char.portrait_url(32) if char else "https://images.evetech.net/characters/1/portrait?size=32"
