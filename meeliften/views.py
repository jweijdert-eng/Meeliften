"""Views — Meeliften."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from . import meldingen
from .forms import RitForm, VraagForm
from .models import GEEN_PLEK_DAGEN, Rit, SchipType, Vraag
from .schepen import ZONDER_SMB_IDS


def _beheerder(user) -> bool:
    return user.has_perm("meeliften.manage")


@login_required
@permission_required("meeliften.basic_access")
def index(request: WSGIRequest) -> HttpResponse:
    """Eén lijst met wie ruimte heeft, plus je eigen ruimte en verzoeken."""
    schip = request.GET.get("schip", "")

    ritten = list(Rit.objects.zichtbaar().select_related("piloot__profile__main_character", "character"))
    if schip in SchipType.values:
        ritten = [r for r in ritten if r.schip_type == schip]
    for rit in ritten:
        rit.vraag_form = VraagForm(rit=rit, prefix=f"r{rit.pk}")

    # Weggehaalde ruimte blijft hier staan zolang er nog iets afgeleverd moet worden.
    mijn_ritten = (
        Rit.objects.filter(piloot=request.user)
        .filter(Q(status__in=[Rit.Status.OPEN, Rit.Status.VOL]) | Q(vragen__status=Vraag.Status.TOEGEZEGD))
        .distinct()
        .prefetch_related("vragen__aanvrager__profile__main_character", "vragen__character")
    )
    mijn_verzoeken = (
        Vraag.objects.filter(aanvrager=request.user)
        .filter(
            Q(status__in=[Vraag.Status.AANGEVRAAGD, Vraag.Status.TOEGEZEGD])
            | Q(status=Vraag.Status.GEWEIGERD, gewijzigd__gte=timezone.now() - timedelta(days=GEEN_PLEK_DAGEN))
        )
        .select_related("rit__piloot__profile__main_character")
    )

    context = {
        "ritten": ritten,
        "mijn_ritten": mijn_ritten,
        "mijn_verzoeken": mijn_verzoeken,
        "schip": schip,
        "schip_types": SchipType.choices,
    }
    return render(request, "meeliften/index.html", context)


@login_required
@permission_required("meeliften.basic_access")
def rit_form(request: WSGIRequest, rit_id: int | None = None) -> HttpResponse:
    rit = get_object_or_404(Rit, pk=rit_id) if rit_id else None
    if rit and rit.piloot != request.user and not _beheerder(request.user):
        return HttpResponseForbidden()
    form = RitForm(request.POST or None, instance=rit, user=rit.piloot if rit else request.user)
    if request.method == "POST" and form.is_valid():
        nieuw = form.save(commit=False)
        if not rit:
            nieuw.piloot = request.user
        nieuw.save()
        messages.success(request, _("Opgeslagen."))
        return redirect("meeliften:index")
    return render(request, "meeliften/rit_form.html", {"form": form, "rit": rit, "zonder_smb_ids": ZONDER_SMB_IDS})


@login_required
@permission_required("meeliften.basic_access")
def plekje(request: WSGIRequest, rit_id: int) -> HttpResponse:
    """'Ik wil mee': het vakje op het bord post hierheen. Bij een fout tonen we het los."""
    rit = get_object_or_404(Rit.objects.zichtbaar().filter(status=Rit.Status.OPEN), pk=rit_id)
    if rit.piloot == request.user:
        messages.warning(request, _("Dat is je eigen ruimte."))
        return redirect("meeliften:index")
    form = VraagForm(request.POST or None, rit=rit, prefix=f"r{rit.pk}")
    if request.method == "POST" and form.is_valid():
        vraag = form.save(commit=False)
        vraag.aanvrager = request.user
        vraag.character = getattr(request.user.profile, "main_character", None)
        vraag.rit = rit
        vraag.status = Vraag.Status.AANGEVRAAGD
        vraag.save()
        meldingen.plekje_gevraagd(vraag)
        messages.success(request, _("Gevraagd! %(naam)s krijgt een melding.") % {"naam": meldingen.naam(rit.piloot)})
        return redirect("meeliften:index")
    return render(request, "meeliften/vraag_form.html", {"form": form, "rit": rit})


def _geen_plek(vraag, melding) -> None:
    vraag.status, vraag.vervoerder = Vraag.Status.GEWEIGERD, None
    vraag.save(update_fields=["status", "vervoerder", "gewijzigd"])
    melding()


@login_required
@permission_required("meeliften.basic_access")
@require_POST
def rit_status(request: WSGIRequest, rit_id: int, status: str) -> HttpResponse:
    """Vol / weer ruimte / weghalen."""
    rit = get_object_or_404(Rit, pk=rit_id)
    if rit.piloot != request.user and not _beheerder(request.user):
        return HttpResponseForbidden()
    if status not in Rit.Status.values:
        return redirect("meeliften:index")
    with transaction.atomic():
        rit.status = status
        rit.save(update_fields=["status"])
        if status in (Rit.Status.VERTROKKEN, Rit.Status.GEANNULEERD):
            # Wie nog op antwoord wacht, krijgt "geen plek". Wie al mee mag, blijft mee mogen
            # (de piloot rondt dat af met Afgeleverd of Toch niet).
            for vraag in rit.vragen.filter(status=Vraag.Status.AANGEVRAAGD):
                _geen_plek(vraag, lambda v=vraag: meldingen.geweigerd(v, rit))
    messages.info(request, _("Je ruimte staat nu op: %(s)s") % {"s": rit.get_status_display()})
    return redirect("meeliften:index")


@login_required
@permission_required("meeliften.basic_access")
@require_POST
def vraag_actie(request: WSGIRequest, vraag_id: int, actie: str) -> HttpResponse:
    """Ja, nee, toch niet, afgeleverd, intrekken."""
    vraag = get_object_or_404(Vraag.objects.select_related("rit"), pk=vraag_id)
    user = request.user
    is_piloot = bool(vraag.rit_id) and vraag.rit.piloot_id == user.pk
    is_vervoerder = vraag.vervoerder_id == user.pk
    is_aanvrager = vraag.aanvrager_id == user.pk
    beheer = _beheerder(user)

    if actie == "ja" and vraag.status == Vraag.Status.AANGEVRAAGD and (is_piloot or beheer):
        vraag.status, vraag.vervoerder = Vraag.Status.TOEGEZEGD, vraag.rit.piloot
        vraag.save(update_fields=["status", "vervoerder", "gewijzigd"])
        meldingen.geaccepteerd(vraag)
    elif actie == "nee" and vraag.status == Vraag.Status.AANGEVRAAGD and (is_piloot or beheer):
        _geen_plek(vraag, lambda: meldingen.geweigerd(vraag, vraag.rit))
    elif actie == "toch-niet" and vraag.status == Vraag.Status.TOEGEZEGD and (is_vervoerder or beheer):
        vervoerder = vraag.vervoerder
        _geen_plek(vraag, lambda: meldingen.teruggetrokken(vraag, vervoerder))
    elif actie == "afgeleverd" and vraag.status == Vraag.Status.TOEGEZEGD and (is_vervoerder or is_aanvrager or beheer):
        vraag.status = Vraag.Status.AFGELEVERD
        vraag.save(update_fields=["status", "gewijzigd"])
        meldingen.afgeleverd(vraag, user)
    elif actie == "intrekken" and (is_aanvrager or beheer) and vraag.status in (
        Vraag.Status.AANGEVRAAGD, Vraag.Status.TOEGEZEGD, Vraag.Status.GEWEIGERD
    ):
        ander = vraag.vervoerder or (vraag.rit.piloot if vraag.rit_id and vraag.actief else None)
        vraag.status = Vraag.Status.GEANNULEERD
        vraag.save(update_fields=["status", "gewijzigd"])
        if ander:
            meldingen.geannuleerd_door_aanvrager(vraag, ander)
    else:
        messages.warning(request, _("Dat kan niet (meer)."))
    return redirect("meeliften:index")
