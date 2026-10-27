"""Forms — Meeliften."""

from django import forms
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter

from .models import Rit, Vraag
from .schepen import herken


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
        for naam, veld in self.fields.items():
            css = "form-select" if isinstance(veld.widget, forms.Select) else "form-control"
            veld.widget.attrs.setdefault("class", css)
            if naam in ("van", "naar"):
                veld.widget.attrs.update({"list": "ml-systemen", "autocomplete": "off", "data-ml-systeem": "1"})

    def clean(self):
        data = super().clean()
        if data.get("van") and data.get("van", "").strip().lower() == data.get("naar", "").strip().lower():
            raise forms.ValidationError(_("Van en naar zijn hetzelfde."))
        return data


class RitForm(_EigenCharacterForm):
    class Meta:
        model = Rit
        fields = ["character", "schip_type", "schip_naam", "vertrek", "van", "naar", "vrij_m3", "vrij_schepen", "opmerking"]
        labels = {
            "character": _("Piloot"),
            "schip_type": _("Schip"),
            "schip_naam": _("Scheepstype / naam"),
            "vertrek": _("Vertrek (EVE-tijd)"),
            "vrij_m3": _("Vrij (m³)"),
            "vrij_schepen": _("Vrije SMB-plekken"),
        }
        widgets = {
            "vertrek": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "opmerking": forms.Textarea(attrs={"rows": 2, "placeholder": _("Bijv. 'alleen gepackagede schepen', 'via Thera'")}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["schip_naam"].widget.attrs.update({"list": "ml-schepen", "autocomplete": "off", "data-ml-schip": "1"})

    def clean(self):
        data = super().clean()
        if not data.get("vrij_m3") and not data.get("vrij_schepen"):
            raise forms.ValidationError(_("Vul vrije m³ of vrije SMB-plekken in (of allebei)."))
        return data

    def save(self, commit=True):
        rit = super().save(commit=False)
        # Herkend scheepstype → eigen icoontje, en de klasse volgt het schip ('Nyx' is altijd een super).
        rit.schip_type_id, klasse = herken(rit.schip_naam)
        if klasse:
            rit.schip_type = klasse
        if commit:
            rit.save()
        return rit


class VraagForm(_EigenCharacterForm):
    class Meta:
        model = Vraag
        fields = ["character", "van", "naar", "wat", "volume_m3", "schepen", "uiterlijk", "opmerking"]
        labels = {
            "character": _("Voor"),
            "wat": _("Wat moet er mee?"),
            "volume_m3": _("Volume (m³)"),
            "schepen": _("Opgebouwde schepen"),
            "uiterlijk": _("Uiterlijk nodig op"),
        }
        widgets = {
            "uiterlijk": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "opmerking": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, rit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rit = rit
        if rit:
            for naam in ("van", "naar"):
                self.fields[naam].disabled = True
                self.initial[naam] = getattr(rit, naam)

    def clean(self):
        data = super().clean()
        if not data.get("volume_m3") and not data.get("schepen"):
            raise forms.ValidationError(_("Vul een volume of een aantal schepen in."))
        rit = self.rit
        if rit:
            m3, schepen = rit.nog_vrij()
            if data.get("volume_m3") and rit.vrij_m3 is None:
                self.add_error("volume_m3", _("Deze rit neemt alleen schepen mee."))
            elif data.get("volume_m3") and m3 is not None and data["volume_m3"] > m3:
                self.add_error("volume_m3", _("Er is nog maar %(m3)s m³ vrij.") % {"m3": f"{m3:,}".replace(",", ".")})
            if data.get("schepen") and rit.vrij_schepen is None:
                self.add_error("schepen", _("Deze rit heeft geen SMB-plekken."))
            elif data.get("schepen") and schepen is not None and data["schepen"] > schepen:
                self.add_error("schepen", _("Er zijn nog maar %(n)s SMB-plekken vrij.") % {"n": schepen})
        return data
