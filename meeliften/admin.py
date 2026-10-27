"""Admin — Meeliften."""

from django.contrib import admin

from .models import Rit, Vraag


class VraagInline(admin.TabularInline):
    model = Vraag
    fields = ("aanvrager", "wat", "van", "naar", "volume_m3", "schepen", "status")
    readonly_fields = ("aanvrager",)
    extra = 0


@admin.register(Rit)
class RitAdmin(admin.ModelAdmin):
    list_display = ("__str__", "piloot", "vrij_m3", "vrij_schepen", "status", "aangemaakt")
    list_filter = ("status", "schip_type")
    search_fields = ("schip_naam", "piloot__username")
    inlines = [VraagInline]


@admin.register(Vraag)
class VraagAdmin(admin.ModelAdmin):
    list_display = ("wat", "van", "naar", "aanvrager", "vervoerder", "status", "aangemaakt")
    list_filter = ("status",)
    search_fields = ("wat", "van", "naar", "aanvrager__username")
