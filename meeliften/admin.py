"""Admin — Meeliften."""

from django.contrib import admin

from .models import Rit, Vraag


class VraagInline(admin.TabularInline):
    model = Vraag
    fields = ("aanvrager", "soort", "volume_m3", "smb_m3", "opmerking", "status")
    readonly_fields = ("aanvrager",)
    extra = 0


@admin.register(Rit)
class RitAdmin(admin.ModelAdmin):
    list_display = ("__str__", "piloot", "vrij_m3", "vrij_smb_m3", "status", "aangemaakt")
    list_filter = ("status", "schip_type")
    search_fields = ("piloot__username",)
    inlines = [VraagInline]


@admin.register(Vraag)
class VraagAdmin(admin.ModelAdmin):
    list_display = ("__str__", "aanvrager", "vervoerder", "status", "aangemaakt")
    list_filter = ("status", "soort")
    search_fields = ("opmerking", "aanvrager__username")
