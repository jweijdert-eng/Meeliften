from django.db import migrations

# Klassen zonder ship maintenance bay (zie schepen.ZONDER_SMB); hier vastgezet zodat de
# migratie niet verandert als die lijst later groeit.
ZONDER_SMB = ["jf"]


def smb_leegmaken(apps, schema_editor):
    Rit = apps.get_model("meeliften", "Rit")
    Rit.objects.filter(schip_type__in=ZONDER_SMB).update(vrij_smb_m3=None)


class Migration(migrations.Migration):
    """Jump freighters hebben geen SMB: bestaande SMB-waarden bij JF's leegmaken."""

    dependencies = [
        ("meeliften", "0008_smb_in_m3"),
    ]

    operations = [
        migrations.RunPython(smb_leegmaken, migrations.RunPython.noop),
    ]
