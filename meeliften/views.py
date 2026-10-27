"""Views — Meeliften."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from . import meldingen
from .forms import RitForm, VraagForm
from .models import Rit, SchipType, Vraag
from .schepen import zoek_namen


def _beheerder(user) -> bool:
    return user.has_perm("meeliften.manage")


def _zoek(qs, q: str):
    if q:
        qs = qs.filter(Q(van__icontains=q) | Q(naar__icontains=q))
    return qs


@login_required
@permission_required("meeliften.basic_access")
def index(request: WSGIRequest) -> HttpResponse:
    """Het bord: aangeboden ritten, open vragen en je eigen lopende zaken."""
    q = request.GET.get("q", "").strip()
    schip = request.GET.get("schip", "")

    ritten = _zoek(Rit.objects.zichtbaar(), q).select_related("piloot__profile__main_character", "character")
    if schip in SchipType.values:
        ritten = ritten.filter(schip_type=schip)
    vragen = _zoek(Vraag.objects.zichtbaar(), q).select_related("aanvrager__profile__main_character", "character")

    mijn_ritten = (
        Rit.objects.filter(piloot=request.user, status__in=[Rit.Status.OPEN, Rit.Status.VOL])
        .prefetch_related("vragen__aanvrager__profile__main_character", "vragen__character")
    )
    mijn_vragen = (
        Vraag.objects.filter(aanvrager=request.user)
        .exclude(status__in=[Vraag.Status.AFGELEVERD, Vraag.Status.GEANNULEERD])
        .select_related("rit", "vervoerder__profile__main_character")
    )
    ik_vervoer = (
        Vraag.objects.filter(vervoerder=request.user, status=Vraag.Status.TOEGEZEGD, rit__isnull=True)
        .select_related("aanvrager__profile__main_character", "character")
    )

    context = {
        "ritten": ritten,
        "vragen": vragen,
        "mijn_ritten": mijn_ritten,
        "mijn_vragen": mijn_vragen,
        "ik_vervoer": ik_vervoer,
        "q": q,
        "schip": schip,
        "schip_types": SchipType.choices,
        "beheerder": _beheerder(request.user),
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
        messages.success(request, _("Rit opgeslagen."))
        return redirect("meeliften:index")
    return render(request, "meeliften/rit_form.html", {"form": form, "rit": rit})


@login_required
@permission_required("meeliften.basic_access")
def vraag_form(request: WSGIRequest, rit_id: int | None = None) -> HttpResponse:
    """Losse vraag op het bord, of (met rit_id) een plekje vragen in die rit."""
    rit = get_object_or_404(Rit.objects.zichtbaar(), pk=rit_id) if rit_id else None
    if rit and rit.piloot == request.user:
        messages.warning(request, _("Dat is je eigen rit."))
        return redirect("meeliften:index")
    form = VraagForm(request.POST or None, user=request.user, rit=rit)
    if request.method == "POST" and form.is_valid():
        vraag = form.save(commit=False)
        vraag.aanvrager = request.user
        if rit:
            vraag.rit = rit
            vraag.van, vraag.naar = rit.van, rit.naar
            vraag.status = Vraag.Status.AANGEVRAAGD
        vraag.save()
        if rit:
            meldingen.plekje_gevraagd(vraag)
            messages.success(request, _("Gevraagd! De piloot krijgt een melding."))
        else:
            messages.success(request, _("Je vraag staat op het bord."))
        return redirect("meeliften:index")
    return render(request, "meeliften/vraag_form.html", {"form": form, "rit": rit})


@login_required
@permission_required("meeliften.basic_access")
@require_POST
def rit_status(request: WSGIRequest, rit_id: int, status: str) -> HttpResponse:
    """Piloot zet zijn rit op open / vol / vertrokken / geannuleerd."""
    rit = get_object_or_404(Rit, pk=rit_id)
    if rit.piloot != request.user and not _beheerder(request.user):
        return HttpResponseForbidden()
    if status not in Rit.Status.values:
        return redirect("meeliften:index")
    with transaction.atomic():
        rit.status = status
        rit.save(update_fields=["status"])
        if status in (Rit.Status.VERTROKKEN, Rit.Status.GEANNULEERD):
            # Openstaande aanvragen gaan terug naar het bord; bij annuleren ook de toezeggingen.
            terug = [Vraag.Status.AANGEVRAAGD]
            if status == Rit.Status.GEANNULEERD:
                terug.append(Vraag.Status.TOEGEZEGD)
            for vraag in rit.vragen.filter(status__in=terug):
                was = vraag.status
                vraag.rit, vraag.vervoerder, vraag.status = None, None, Vraag.Status.OPEN
                vraag.save(update_fields=["rit", "vervoerder", "status"])
                if was == Vraag.Status.TOEGEZEGD:
                    meldingen.teruggetrokken(vraag, rit.piloot)
                else:
                    meldingen.geweigerd(vraag, rit)
    messages.info(request, _("Rit staat nu op: %(s)s") % {"s": rit.get_status_display()})
    return redirect("meeliften:index")


@login_required
@permission_required("meeliften.basic_access")
@require_POST
def vraag_actie(request: WSGIRequest, vraag_id: int, actie: str) -> HttpResponse:
    """Alle stappen in een aanvraag: accepteren, weigeren, meenemen, terugtrekken, afgeleverd, annuleren."""
    vraag = get_object_or_404(Vraag, pk=vraag_id)
    user = request.user
    is_piloot = vraag.rit_id and vraag.rit.piloot == user
    is_vervoerder = vraag.vervoerder_id == user.pk
    is_aanvrager = vraag.aanvrager_id == user.pk
    beheer = _beheerder(user)

    if actie == "accepteer" and vraag.status == Vraag.Status.AANGEVRAAGD and (is_piloot or beheer):
        vraag.status, vraag.vervoerder = Vraag.Status.TOEGEZEGD, vraag.rit.piloot
        vraag.save(update_fields=["status", "vervoerder"])
        meldingen.geaccepteerd(vraag)
    elif actie == "weiger" and vraag.status == Vraag.Status.AANGEVRAAGD and (is_piloot or beheer):
        rit = vraag.rit
        vraag.status, vraag.rit = Vraag.Status.OPEN, None
        vraag.save(update_fields=["status", "rit"])
        meldingen.geweigerd(vraag, rit)
    elif actie == "meenemen" and vraag.status == Vraag.Status.OPEN and not is_aanvrager:
        vraag.status, vraag.vervoerder = Vraag.Status.TOEGEZEGD, user
        vraag.save(update_fields=["status", "vervoerder"])
        meldingen.geaccepteerd(vraag)
    elif actie == "terugtrekken" and vraag.status == Vraag.Status.TOEGEZEGD and (is_vervoerder or beheer):
        vervoerder = vraag.vervoerder
        vraag.status, vraag.vervoerder, vraag.rit = Vraag.Status.OPEN, None, None
        vraag.save(update_fields=["status", "vervoerder", "rit"])
        meldingen.teruggetrokken(vraag, vervoerder)
    elif actie == "afgeleverd" and vraag.status == Vraag.Status.TOEGEZEGD and (is_vervoerder or is_aanvrager or beheer):
        vraag.status = Vraag.Status.AFGELEVERD
        vraag.save(update_fields=["status"])
        meldingen.afgeleverd(vraag, user)
    elif actie == "annuleer" and vraag.actief and (is_aanvrager or beheer):
        ander = vraag.vervoerder or (vraag.rit.piloot if vraag.rit_id else None)
        vraag.status = Vraag.Status.GEANNULEERD
        vraag.save(update_fields=["status"])
        if ander:
            meldingen.geannuleerd_door_aanvrager(vraag, ander)
    else:
        messages.warning(request, _("Dat kan niet (meer)."))
        return redirect("meeliften:index")
    messages.success(request, _("Gelukt."))
    return redirect("meeliften:index")


@login_required
@permission_required("meeliften.basic_access")
def systemen(request: WSGIRequest) -> JsonResponse:
    """Systeemnamen voor het invulveld; uit eve_sde (CorpTools) of eveuniverse, wat er is."""
    q = request.GET.get("q", "").strip()
    namen: list[str] = []
    if len(q) >= 2:
        try:
            from eve_sde.models import SolarSystem

            # eve_sde vertaalt `name` via modeltranslation; in een Nederlandse sessie wordt dat
            # stilletjes `name_nl`, en die is leeg. Systeemnamen zijn in elke taal hetzelfde.
            with translation.override("en"):
                namen = list(SolarSystem.objects.filter(name__istartswith=q).order_by("name").values_list("name", flat=True)[:15])
        except Exception:  # noqa: BLE001
            try:
                from eveuniverse.models import EveSolarSystem

                namen = list(EveSolarSystem.objects.filter(name__istartswith=q).order_by("name").values_list("name", flat=True)[:15])
            except Exception:  # noqa: BLE001
                namen = []
    return JsonResponse({"systemen": namen})


@login_required
@permission_required("meeliften.basic_access")
def schepen(request: WSGIRequest) -> JsonResponse:
    """Capital-scheepsnamen voor het invulveld."""
    q = request.GET.get("q", "").strip()
    return JsonResponse({"schepen": zoek_namen(q) if len(q) >= 2 else []})
