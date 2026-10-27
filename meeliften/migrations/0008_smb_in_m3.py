from django.db import migrations, models


class Migration(migrations.Migration):
    """SMB telt voortaan in m³ in plaats van in plekken/schepen."""

    dependencies = [
        ("meeliften", "0007_soort_en_ja_nee"),
    ]

    operations = [
        migrations.RenameField(model_name="rit", old_name="vrij_schepen", new_name="vrij_smb_m3"),
        migrations.AlterField(
            model_name="rit",
            name="vrij_smb_m3",
            field=models.PositiveIntegerField(blank=True, help_text="Vrije ship maintenance bay in m³", null=True),
        ),
        migrations.RenameField(model_name="vraag", old_name="schepen", new_name="smb_m3"),
        migrations.AlterField(
            model_name="vraag",
            name="smb_m3",
            field=models.PositiveIntegerField(
                blank=True, help_text="Gefitte schepen (ship maintenance bay), in m³", null=True
            ),
        ),
    ]
