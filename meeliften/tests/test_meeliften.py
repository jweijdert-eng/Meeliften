"""Meeliften: het hele bord via de testclient. Draaien vanuit myauth/:
manage.py test meeliften --keepdb --noinput"""

from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.notifications.models import Notification
from allianceauth.tests.auth_utils import AuthUtils

from meeliften.models import Rit, Vraag


def client(user) -> Client:
    c = Client(HTTP_HOST="localhost")
    c.force_login(user)
    return c


def lid(naam, char_id, *perms):
    user = AuthUtils.create_user(naam)
    char = AuthUtils.add_main_character_2(user, naam.title(), char_id, corp_id=98000001, corp_name="Testcorp")
    CharacterOwnership.objects.create(user=user, character=char, owner_hash=f"h-{char_id}")
    for perm in ("meeliften.basic_access", *perms):
        AuthUtils.add_permission_to_user_by_name(perm, user)
    return user


class Basis(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.piloot = lid("ml_piloot", 9201001)
        cls.vrager = lid("ml_vrager", 9201002)
        cls.ander = lid("ml_ander", 9201003)
        cls.beheer = lid("ml_beheer", 9201004, "meeliften.manage")
        cls.buiten = AuthUtils.create_user("ml_buiten")

    def rit(self, **kw) -> Rit:
        data = dict(piloot=self.piloot, schip_id=28850, vrij_m3=300_000, vrij_schepen=None)
        data.update(kw)
        return Rit.objects.create(**data)

    def post(self, user, naam, *args, data=None):
        return client(user).post(reverse(f"meeliften:{naam}", args=args), data or {})

    def wil_mee(self, rit, user=None, soort="items", hoeveel=50_000, opmerking="Muninn + ammo"):
        """Wat het 'Ik wil mee'-vakje op het bord verstuurt (velden met prefix r<rit-id>)."""
        p = f"r{rit.pk}-"
        return self.post(user or self.vrager, "plekje", rit.pk,
                         data={p + "soort": soort, p + "hoeveel": hoeveel, p + "opmerking": opmerking})

    def vraag(self, **kw) -> Vraag:
        data = dict(aanvrager=self.vrager, rit=self.rit(), soort="items", volume_m3=5, status="aangevraagd")
        data.update(kw)
        return Vraag.objects.create(**data)


class TestBord(Basis):
    def test_zonder_permissie_geen_toegang(self):
        r = client(self.buiten).get(reverse("meeliften:index"))
        self.assertNotEqual(r.status_code, 200)

    def test_bord_laadt_met_ik_wil_mee(self):
        rit = self.rit()
        r = client(self.ander).get(reverse("meeliften:index"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ark")
        self.assertContains(r, "/types/28850/")
        self.assertContains(r, "300.000")
        self.assertContains(r, "Ik wil mee")
        self.assertContains(r, f'action="{reverse("meeliften:plekje", args=[rit.pk])}"')
        self.assertNotContains(r, "Gezocht")

    def test_alleen_passende_soorten(self):
        cargo = self.rit()
        smb = self.rit(schip_id=23911, vrij_m3=None, vrij_schepen=3)
        beide = self.rit(schip_id=23913, vrij_m3=10_000, vrij_schepen=2)
        r = client(self.ander).get(reverse("meeliften:index"))
        soorten = {rit.pk: [w for w, _ in rit.vraag_form.fields["soort"].choices] for rit in r.context["ritten"]}
        self.assertEqual(soorten[cargo.pk], ["items", "repackaged"])
        self.assertEqual(soorten[smb.pk], ["gefit"])
        self.assertEqual(soorten[beide.pk], ["items", "repackaged", "gefit"])

    def test_ruimte_zonder_m3_en_smb_breekt_het_bord_niet(self):
        self.rit(vrij_m3=None, vrij_schepen=None)  # kan via de admin
        self.assertEqual(client(self.ander).get(reverse("meeliften:index")).status_code, 200)

    def test_eigen_ruimte_geen_knop(self):
        self.rit()
        r = client(self.piloot).get(reverse("meeliften:index"))
        self.assertContains(r, "jouw schip")
        self.assertNotContains(r, 'data-bs-target="#mee-')

    def test_ander_mag_rit_niet_bewerken(self):
        rit = self.rit()
        self.assertEqual(client(self.ander).get(reverse("meeliften:rit_bewerk", args=[rit.pk])).status_code, 403)
        self.assertEqual(self.post(self.ander, "rit_status", rit.pk, "vertrokken").status_code, 403)
        self.assertEqual(client(self.beheer).get(reverse("meeliften:rit_bewerk", args=[rit.pk])).status_code, 200)


class TestRit(Basis):
    def test_ruimte_aanbieden(self):
        r = self.post(self.piloot, "rit_nieuw", data={
            "character": self.piloot.profile.main_character.pk, "schip_id": 23911, "vrij_schepen": 3,
        })
        self.assertEqual(r.status_code, 302)
        rit = Rit.objects.get()
        self.assertEqual((rit.schip_naam, rit.schip_type, rit.vrij_schepen), ("Thanatos", "carrier", 3))

    def test_zonder_ruimte_geweigerd(self):
        self.assertEqual(self.post(self.piloot, "rit_nieuw", data={"schip_id": 28850}).status_code, 200)
        self.assertFalse(Rit.objects.exists())

    def test_onbekend_schip_geweigerd(self):
        self.post(self.piloot, "rit_nieuw", data={"schip_id": 587, "vrij_m3": 5})
        self.assertFalse(Rit.objects.exists())

    def test_dropdown_heeft_scheepsnamen(self):
        r = client(self.piloot).get(reverse("meeliften:rit_nieuw"))
        self.assertContains(r, '<optgroup label="Jump Freighter">')
        self.assertContains(r, ">Komodo</option>")

    def test_icoon_en_klasse_volgen_het_schip(self):
        rit = self.rit(schip_id=23913)
        self.assertEqual((rit.schip_naam, rit.schip_type), ("Nyx", "super"))
        oud = self.rit(schip_id=None, schip_type="titan")
        self.assertIn("/types/11567/", oud.icoon)

    def test_oude_ruimte_verdwijnt(self):
        oud = self.rit()
        Rit.objects.filter(pk=oud.pk).update(aangemaakt=timezone.now() - timedelta(days=40))
        self.rit(status="vertrokken")
        vers = self.rit()
        self.assertEqual(list(Rit.objects.zichtbaar()), [vers])

    def test_weghalen_geeft_wachtenden_geen_plek_maar_houdt_toezeggingen(self):
        rit = self.rit()
        wacht = self.vraag(rit=rit)
        mag = self.vraag(rit=rit, aanvrager=self.ander, status="toegezegd", vervoerder=self.piloot)
        self.post(self.piloot, "rit_status", rit.pk, "vertrokken")
        wacht.refresh_from_db(); mag.refresh_from_db()
        self.assertEqual((wacht.status, mag.status), ("geweigerd", "toegezegd"))
        self.assertTrue(Notification.objects.filter(user=self.vrager, title__contains="geen plek").exists())
        r = client(self.piloot).get(reverse("meeliften:index"))
        self.assertIn(rit, list(r.context["mijn_ritten"]), "weggehaald maar nog af te leveren blijft zichtbaar")


class TestIkWilMee(Basis):
    def test_losse_items_ja_en_afleveren(self):
        rit = self.rit()
        self.assertEqual(self.wil_mee(rit).status_code, 302)
        vraag = Vraag.objects.get()
        self.assertEqual((vraag.status, vraag.soort, vraag.volume_m3, vraag.schepen), ("aangevraagd", "items", 50_000, None))
        self.assertEqual(vraag.character, self.vrager.profile.main_character)
        melding = Notification.objects.get(user=self.piloot, title__contains="wil mee")
        self.assertIn("50.000 m³ losse items — Muninn + ammo", melding.message)

        self.post(self.piloot, "vraag_actie", vraag.pk, "ja")
        vraag.refresh_from_db()
        self.assertEqual((vraag.status, vraag.vervoerder), ("toegezegd", self.piloot))
        self.assertTrue(Notification.objects.filter(user=self.vrager, title__contains="je mag mee").exists())
        self.assertEqual(rit.nog_vrij(), (250_000, None))

        self.post(self.vrager, "vraag_actie", vraag.pk, "afgeleverd")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "afgeleverd")
        self.assertEqual(rit.nog_vrij(), (300_000, None))

    def test_repackaged_telt_als_m3(self):
        rit = self.rit()
        self.wil_mee(rit, soort="repackaged", hoeveel=120_000, opmerking="Raven")
        vraag = Vraag.objects.get()
        self.assertEqual((vraag.volume_m3, vraag.schepen), (120_000, None))
        self.assertEqual(vraag.omschrijving, "120.000 m³ gerepackaged schip — Raven")

    def test_gefit_schip_telt_in_smb(self):
        rit = self.rit(schip_id=23911, vrij_m3=None, vrij_schepen=3)
        self.wil_mee(rit, soort="gefit", hoeveel=2, opmerking="Ishtar")
        vraag = Vraag.objects.get()
        self.assertEqual((vraag.schepen, vraag.volume_m3), (2, None))
        self.assertEqual(vraag.omschrijving, "2 gefitte schepen — Ishtar")
        self.post(self.piloot, "vraag_actie", vraag.pk, "ja")
        self.assertEqual(rit.nog_vrij(), (None, 1))

    def test_soort_die_niet_past_geweigerd(self):
        smb = self.rit(schip_id=23911, vrij_m3=None, vrij_schepen=3)
        self.assertEqual(self.wil_mee(smb, soort="items", hoeveel=5).status_code, 200)
        cargo = self.rit()
        self.wil_mee(cargo, soort="gefit", hoeveel=1)
        self.assertFalse(Vraag.objects.exists())

    def test_meer_dan_vrij_geweigerd(self):
        self.wil_mee(self.rit(vrij_m3=10_000))
        self.wil_mee(self.rit(vrij_m3=None, vrij_schepen=1), soort="gefit", hoeveel=2)
        self.assertFalse(Vraag.objects.exists())

    def test_hoeveel_verplicht(self):
        self.wil_mee(self.rit(), hoeveel="")
        self.assertFalse(Vraag.objects.exists())

    def test_eigen_ruimte_niet(self):
        self.wil_mee(self.rit(), user=self.piloot)
        self.assertFalse(Vraag.objects.exists())

    def test_volle_ruimte_niet(self):
        rit = self.rit(status="vol")
        self.assertEqual(self.wil_mee(rit).status_code, 404)

    def test_nee_geeft_geen_plek(self):
        vraag = self.vraag()
        self.post(self.piloot, "vraag_actie", vraag.pk, "nee")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "geweigerd")
        self.assertTrue(Notification.objects.filter(user=self.vrager, title__contains="geen plek").exists())
        r = client(self.vrager).get(reverse("meeliften:index"))
        self.assertContains(r, "Geen plek")

    def test_ander_kan_geen_ja_zeggen(self):
        vraag = self.vraag()
        self.post(self.ander, "vraag_actie", vraag.pk, "ja")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "aangevraagd")

    def test_toch_niet(self):
        vraag = self.vraag(status="toegezegd", vervoerder=self.piloot)
        self.post(self.piloot, "vraag_actie", vraag.pk, "toch-niet")
        vraag.refresh_from_db()
        self.assertEqual((vraag.status, vraag.vervoerder), ("geweigerd", None))
        self.assertTrue(Notification.objects.filter(user=self.vrager, title__contains="vervalt").exists())

    def test_intrekken_meldt_piloot(self):
        vraag = self.vraag(status="toegezegd", vervoerder=self.piloot)
        self.post(self.vrager, "vraag_actie", vraag.pk, "intrekken")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "geannuleerd")
        self.assertTrue(Notification.objects.filter(user=self.piloot, title__contains="ingetrokken").exists())

    def test_geen_plek_wegklikken_zonder_melding(self):
        vraag = self.vraag(status="geweigerd")
        self.post(self.vrager, "vraag_actie", vraag.pk, "intrekken")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "geannuleerd")
        self.assertFalse(Notification.objects.filter(user=self.piloot).exists())

    def test_oude_geen_plek_verdwijnt_uit_mijn_verzoeken(self):
        vraag = self.vraag(status="geweigerd")
        Vraag.objects.filter(pk=vraag.pk).update(gewijzigd=timezone.now() - timedelta(days=5))
        r = client(self.vrager).get(reverse("meeliften:index"))
        self.assertEqual(list(r.context["mijn_verzoeken"]), [])
