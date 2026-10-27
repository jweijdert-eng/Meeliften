"""Forms — Meeliften."""

from django import forms
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter

from .models import Rit, Vraag
from .schepen import PER_ID, ZONDER_SMB, keuzes


class _EigenCharacterForm(forms.ModelForm):
    """Character-keuze beperkt tot de characters van het eigen account, main voorop."""

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        chars = EveCharacter.objects.filter(character_ownership__user=user).order_by("character_name")
        if chars.exists():
            self.fields["character"].queryset = chars
            self.fields["character"].empty_label = None
            main = getattr(user.profile, "main_character", None)
            if not self.instance.pk and main:
                self.initial.setdefault("character", main.pk)
        else:
            del self.fields["character"]
        for veld in self.fields.values():
            css = "form-select" if isinstance(veld.widget, forms.Select) else "form-control"
            veld.widget.attrs.setdefault("class", css)


class RitForm(_EigenCharacterForm):
    class Meta:
        model = Rit
        fields = ["character", "schip_id", "vrij_m3", "vrij_smb_m3", "opmerking"]
        labels = {
            "character": _("Piloot"),
            "vrij_m3": _("Vrij in cargo / fleet hangar (m³)"),
            "vrij_smb_m3": _("Vrij in de SMB (m³)"),
        }
        help_texts = {
            "vrij_m3": _("Voor losse items en gerepackagede schepen. Leeg laten als je geen cargo-ruimte hebt."),
            "vrij_smb_m3": _("Voor gefitte schepen. Leeg laten als je geen ship maintenance bay hebt."),
        }
        widgets = {
            "opmerking": forms.Textarea(attrs={"rows": 2, "placeholder": _("Bijv. 'alleen gepackagede schepen'")}),
        }

    schip_id = forms.TypedChoiceField(label=_("Schip"), coerce=int, choices=keuzes,
                                      widget=forms.Select(attrs={"class": "form-select"}))

    def clean(self):
        data = super().clean()
        if PER_ID.get(data.get("schip_id"), (None, None))[1] in ZONDER_SMB:
            data["vrij_smb_m3"] = None
        if not data.get("vrij_m3") and not data.get("vrij_smb_m3"):
            raise forms.ValidationError(_("Vul vrije m³ in de cargo of in de SMB in (of allebei)."))
        return data



class VraagForm(forms.ModelForm):
    """'Ik wil mee': soort vracht, hoeveel m³ en een opmerking.

    Het verzoek gaat op naam van je main. Gefitte schepen gaan in de SMB, losse items
    en gerepackagede schepen in de cargo; allebei tellen ze in m³.
    """

    hoeveel = forms.IntegerField(label=_("Hoeveel m³?"), min_value=1,
                                 widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "m³"}))

    class Meta:
        model = Vraag
        fields = ["soort", "opmerking"]
        labels = {"soort": _("Wat moet er mee?"), "opmerking": _("Opmerking")}
        widgets = {
            "soort": forms.RadioSelect,
            "opmerking": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Bijv. Ishtar + ammo, Jita naar Q-02UL")}),
        }

    def __init__(self, *args, rit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rit = rit
        if rit:
            keuzes = soorten_voor(rit)
            self.fields["soort"].choices = keuzes
            if keuzes:
                self.initial.setdefault("soort", keuzes[0][0])

    def clean(self):
        data = super().clean()
        soort, hoeveel, rit = data.get("soort"), data.get("hoeveel"), self.rit
        if not soort or not hoeveel or not rit:
            return data
        m3, smb = rit.nog_vrij()
        if soort == Vraag.Soort.GEFIT:
            if smb is not None and hoeveel > smb:
                self.add_error("hoeveel", _("Er is nog maar %(m3)s m³ vrij in de SMB.") % {"m3": f"{smb:,}".replace(",", ".")})
        elif m3 is not None and hoeveel > m3:
            self.add_error("hoeveel", _("Er is nog maar %(m3)s m³ vrij.") % {"m3": f"{m3:,}".replace(",", ".")})
        return data

    def save(self, commit=True):
        vraag = super().save(commit=False)
        if vraag.soort == Vraag.Soort.GEFIT:
            vraag.smb_m3, vraag.volume_m3 = self.cleaned_data["hoeveel"], None
        else:
            vraag.volume_m3, vraag.smb_m3 = self.cleaned_data["hoeveel"], None
        if commit:
            vraag.save()
        return vraag


def soorten_voor(rit) -> list[tuple[str, str]]:
    """Alleen de soorten die in dit schip passen: cargo voor items/repackaged, SMB voor gefitte schepen."""
    keuzes = []
    if rit.vrij_m3 is not None:
        keuzes += [(Vraag.Soort.ITEMS, Vraag.Soort.ITEMS.label), (Vraag.Soort.REPACKAGED, Vraag.Soort.REPACKAGED.label)]
    if rit.vrij_smb_m3 is not None:
        keuzes.append((Vraag.Soort.GEFIT, Vraag.Soort.GEFIT.label))
    return keuzes
