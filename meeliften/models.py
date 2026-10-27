"""Models — Meeliften.

Een `Rit` is aanbod: een capital-piloot vliegt van A naar B en heeft ruimte over.
Een `Vraag` is iemand die vervoer zoekt. Hangt een vraag aan een rit, dan is het
een plekje-aanvraag bij die piloot; zonder rit staat hij los op het bord tot een
capital-piloot zegt "ik neem het mee".
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter

# Zonder vertrektijd blijft een rit zo lang zichtbaar; met vertrektijd tot een dag erna.
RIT_ZONDER_TIJD_DAGEN = 14
RIT_NA_VERTREK_DAGEN = 1
VRAAG_ZONDER_DATUM_DAGEN = 30


class General(models.Model):
    """Meta-model voor permissies."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", _("Kan Meeliften gebruiken")),
            ("manage", _("Kan alle ritten en vragen beheren")),
        )


class SchipType(models.TextChoices):
    JF = "jf", _("Jump Freighter")
    CARRIER = "carrier", _("Carrier")
    DREAD = "dread", _("Dreadnought")
    FAX = "fax", _("Force Auxiliary")
    SUPER = "super", _("Supercarrier")
    TITAN = "titan", _("Titan")
    RORQUAL = "rorqual", _("Rorqual")
    ANDERS = "anders", _("Anders")


# Icoontje als de piloot geen (herkenbaar) scheepstype invult: een bekend schip per klasse.
STANDAARD_ICOON = {
    SchipType.JF: 28850,        # Ark
    SchipType.CARRIER: 23911,   # Thanatos
    SchipType.DREAD: 19720,     # Revelation
    SchipType.FAX: 37604,       # Apostle
    SchipType.SUPER: 23913,     # Nyx
    SchipType.TITAN: 11567,     # Avatar
    SchipType.RORQUAL: 28352,   # Rorqual
}


class RitQuerySet(models.QuerySet):
    def zichtbaar(self):
        nu = timezone.now()
        return self.filter(status__in=[Rit.Status.OPEN, Rit.Status.VOL]).filter(
            Q(vertrek__isnull=True, aangemaakt__gte=nu - timedelta(days=RIT_ZONDER_TIJD_DAGEN))
            | Q(vertrek__gte=nu - timedelta(days=RIT_NA_VERTREK_DAGEN))
        )


class Rit(models.Model):
    """Aanbod: een capital-piloot met vrije ruimte op een route."""

    class Status(models.TextChoices):
        OPEN = "open", _("Ruimte vrij")
        VOL = "vol", _("Vol")
        VERTROKKEN = "vertrokken", _("Vertrokken")
        GEANNULEERD = "geannuleerd", _("Geannuleerd")

    piloot = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meeliften_ritten")
    character = models.ForeignKey(EveCharacter, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    schip_type = models.CharField(max_length=10, choices=SchipType.choices, default=SchipType.JF)
    schip_naam = models.CharField(max_length=60, blank=True, help_text=_("Bijv. Ark, Nyx, Revelation"))
    schip_type_id = models.PositiveIntegerField(null=True, blank=True, editable=False)
    van = models.CharField(max_length=100)
    naar = models.CharField(max_length=100)
    vertrek = models.DateTimeField(null=True, blank=True, help_text=_("Ongeveer, in EVE-tijd"))
    vrij_m3 = models.PositiveIntegerField(null=True, blank=True, help_text=_("Vrije cargo / fleet hangar in m³"))
    vrij_schepen = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text=_("Aantal schepen dat nog in de ship maintenance bay past")
    )
    opmerking = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    aangemaakt = models.DateTimeField(auto_now_add=True)

    objects = RitQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        ordering = ["vertrek", "-aangemaakt"]
        verbose_name = _("rit")
        verbose_name_plural = _("ritten")

    def __str__(self) -> str:
        return f"{self.get_schip_type_display()} {self.van} → {self.naar}"

    @property
    def icoon(self) -> str:
        type_id = self.schip_type_id or STANDAARD_ICOON.get(self.schip_type)
        if not type_id:
            return ""
        return f"https://images.evetech.net/types/{type_id}/icon?size=64"

    @property
    def toegezegd(self):
        return self.vragen.filter(status=Vraag.Status.TOEGEZEGD)

    def bezet(self) -> tuple[int, int]:
        """(m³, schepen) die al aan deze rit zijn toegezegd."""
        m3 = schepen = 0
        for v in self.toegezegd:
            m3 += v.volume_m3 or 0
            schepen += v.schepen or 0
        return m3, schepen

    def nog_vrij(self) -> tuple[int | None, int | None]:
        m3, schepen = self.bezet()
        return (
            None if self.vrij_m3 is None else max(self.vrij_m3 - m3, 0),
            None if self.vrij_schepen is None else max(self.vrij_schepen - schepen, 0),
        )


class VraagQuerySet(models.QuerySet):
    def zichtbaar(self):
        nu = timezone.now()
        return self.filter(status=Vraag.Status.OPEN).filter(
            Q(uiterlijk__isnull=True, aangemaakt__gte=nu - timedelta(days=VRAAG_ZONDER_DATUM_DAGEN))
            | Q(uiterlijk__gte=nu.date())
        )


class Vraag(models.Model):
    """Iemand zoekt ruimte: los op het bord, of als aanvraag bij een rit."""

    class Status(models.TextChoices):
        OPEN = "open", _("Zoekt vervoer")
        AANGEVRAAGD = "aangevraagd", _("Wacht op piloot")
        TOEGEZEGD = "toegezegd", _("Toegezegd")
        AFGELEVERD = "afgeleverd", _("Afgeleverd")
        GEANNULEERD = "geannuleerd", _("Geannuleerd")

    aanvrager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meeliften_vragen")
    character = models.ForeignKey(EveCharacter, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    van = models.CharField(max_length=100)
    naar = models.CharField(max_length=100)
    wat = models.CharField(max_length=200, help_text=_("Bijv. 'Ishtar + 30k m³ ammo'"))
    volume_m3 = models.PositiveIntegerField(null=True, blank=True, help_text=_("Losse spullen in m³"))
    schepen = models.PositiveSmallIntegerField(default=0, help_text=_("Aantal opgebouwde schepen (voor de SMB)"))
    uiterlijk = models.DateField(null=True, blank=True, help_text=_("Uiterlijk nodig op"))
    opmerking = models.TextField(blank=True)
    rit = models.ForeignKey(Rit, on_delete=models.SET_NULL, null=True, blank=True, related_name="vragen")
    vervoerder = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="meeliften_vervoer"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    aangemaakt = models.DateTimeField(auto_now_add=True)

    objects = VraagQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        ordering = ["uiterlijk", "-aangemaakt"]
        verbose_name = _("vraag")
        verbose_name_plural = _("vragen")

    def __str__(self) -> str:
        return f"{self.wat} ({self.van} → {self.naar})"

    @property
    def actief(self) -> bool:
        return self.status in (self.Status.OPEN, self.Status.AANGEVRAAGD, self.Status.TOEGEZEGD)
