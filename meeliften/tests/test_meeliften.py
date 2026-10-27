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


class TestToegang(Basis):
    def test_zonder_permissie_geen_toegang(self):
        r = client(self.buiten).get(reverse("meeliften:index"))
        self.assertNotEqual(r.status_code, 200)

    def test_bord_laadt(self):
        self.rit()
        Vraag.objects.create(aanvrager=self.vrager, volume_m3=60_000, opmerking="Fuel blocks")
        r = client(self.ander).get(reverse("meeliften:index"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ark")
        self.assertContains(r, "Jump Freighter")
        self.assertContains(r, "/types/28850/")
        self.assertContains(r, "Fuel blocks")
        self.assertContains(r, "300.000")
        self.assertContains(r, "60.000")

    def test_formulieren_laden(self):
        rit = self.rit()
        for naam, args in (("rit_nieuw", []), ("vraag_nieuw", []), ("plekje", [rit.pk]), ("rit_bewerk", [rit.pk])):
            user = self.vrager if naam == "plekje" else self.piloot
            self.assertEqual(client(user).get(reverse(f"meeliften:{naam}", args=args)).status_code, 200, naam)

    def test_vraagformulier_heeft_alleen_de_overgebleven_velden(self):
        r = client(self.vrager).get(reverse("meeliften:vraag_nieuw"))
        self.assertEqual(list(r.context["form"].fields), ["character", "volume_m3", "opmerking"])

    def test_ander_mag_rit_niet_bewerken(self):
        rit = self.rit()
        self.assertEqual(client(self.ander).get(reverse("meeliften:rit_bewerk", args=[rit.pk])).status_code, 403)
        self.assertEqual(self.post(self.ander, "rit_status", rit.pk, "geannuleerd").status_code, 403)
        self.assertEqual(client(self.beheer).get(reverse("meeliften:rit_bewerk", args=[rit.pk])).status_code, 200)


class TestRit(Basis):
    def test_rit_aanbieden(self):
        r = self.post(self.piloot, "rit_nieuw", data={
            "character": self.piloot.profile.main_character.pk, "schip_id": 23911, "vrij_schepen": 3,
        })
        self.assertEqual(r.status_code, 302)
        rit = Rit.objects.get()
        self.assertEqual((rit.piloot, rit.vrij_schepen, rit.vrij_m3), (self.piloot, 3, None))
        self.assertEqual((rit.schip_naam, rit.schip_type), ("Thanatos", "carrier"))
        self.assertIn("/types/23911/", rit.icoon)

    def test_rit_zonder_ruimte_geweigerd(self):
        r = self.post(self.piloot, "rit_nieuw", data={"schip_id": 28850})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Rit.objects.exists())

    def test_icoon_en_klasse_volgen_het_schip(self):
        rit = self.rit(schip_id=23913)
        self.assertEqual((rit.schip_naam, rit.schip_type), ("Nyx", "super"))
        self.assertIn("/types/23913/", rit.icoon)
        oud = self.rit(schip_id=None, schip_type="titan")
        self.assertEqual(oud.schip_naam, "Titan")
        self.assertIn("/types/11567/", oud.icoon)

    def test_onbekend_schip_geweigerd(self):
        r = self.post(self.piloot, "rit_nieuw", data={"schip_id": 587, "vrij_m3": 5})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Rit.objects.exists())

    def test_dropdown_heeft_scheepsnamen(self):
        r = client(self.piloot).get(reverse("meeliften:rit_nieuw"))
        self.assertContains(r, '<optgroup label="Jump Freighter">')
        self.assertContains(r, ">Anshar</option>")
        self.assertContains(r, ">Komodo</option>")

    def test_oude_ritten_verdwijnen(self):
        oud = self.rit()
        Rit.objects.filter(pk=oud.pk).update(aangemaakt=timezone.now() - timedelta(days=40))
        self.rit(status="vertrokken")
        vers = self.rit()
        self.assertEqual(list(Rit.objects.zichtbaar()), [vers])


class TestPlekje(Basis):
    def vraag_plekje(self, rit, **kw):
        data = {"volume_m3": 50_000, "opmerking": "Muninn + ammo"}
        data.update(kw)
        return self.post(self.vrager, "plekje", rit.pk, data=data)

    def test_vragen_accepteren_afleveren(self):
        rit = self.rit()
        self.assertEqual(self.vraag_plekje(rit).status_code, 302)
        vraag = Vraag.objects.get()
        self.assertEqual((vraag.status, vraag.rit), ("aangevraagd", rit))
        melding = Notification.objects.get(user=self.piloot, title__contains="plekje")
        self.assertIn("50.000 m³ — Muninn + ammo", melding.message)

        self.post(self.piloot, "vraag_actie", vraag.pk, "accepteer")
        vraag.refresh_from_db()
        self.assertEqual((vraag.status, vraag.vervoerder), ("toegezegd", self.piloot))
        self.assertTrue(Notification.objects.filter(user=self.vrager, title__contains="je kunt mee").exists())
        self.assertEqual(rit.nog_vrij(), (250_000, None))

        self.post(self.vrager, "vraag_actie", vraag.pk, "afgeleverd")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "afgeleverd")
        self.assertEqual(rit.nog_vrij(), (300_000, None))

    def test_meer_dan_vrij_geweigerd(self):
        rit = self.rit(vrij_m3=10_000)
        self.assertEqual(self.vraag_plekje(rit).status_code, 200)
        self.assertFalse(Vraag.objects.exists())

    def test_smb_rit_alleen_met_opmerking(self):
        rit = self.rit(vrij_m3=None, vrij_schepen=2)
        self.vraag_plekje(rit)
        self.assertFalse(Vraag.objects.exists(), "m³ vragen bij een rit zonder m³ kan niet")
        self.vraag_plekje(rit, volume_m3="", opmerking="1 Ishtar")
        self.assertEqual(Vraag.objects.get().omschrijving, "1 Ishtar")

    def test_lege_vraag_geweigerd(self):
        rit = self.rit()
        self.vraag_plekje(rit, volume_m3="", opmerking="   ")
        self.assertFalse(Vraag.objects.exists())

    def test_eigen_rit_geen_plekje(self):
        rit = self.rit()
        self.post(self.piloot, "plekje", rit.pk, data={"volume_m3": 1})
        self.assertFalse(Vraag.objects.exists())

    def test_weigeren_zet_vraag_los_op_bord(self):
        rit = self.rit()
        self.vraag_plekje(rit)
        vraag = Vraag.objects.get()
        self.post(self.piloot, "vraag_actie", vraag.pk, "weiger")
        vraag.refresh_from_db()
        self.assertEqual((vraag.status, vraag.rit), ("open", None))
        self.assertIn(vraag, Vraag.objects.zichtbaar())

    def test_ander_kan_niet_accepteren(self):
        rit = self.rit()
        self.vraag_plekje(rit)
        vraag = Vraag.objects.get()
        self.post(self.ander, "vraag_actie", vraag.pk, "accepteer")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "aangevraagd")

    def test_rit_annuleren_stuurt_alles_terug(self):
        rit = self.rit()
        self.vraag_plekje(rit)
        toegezegd = Vraag.objects.get()
        self.post(self.piloot, "vraag_actie", toegezegd.pk, "accepteer")
        self.post(self.ander, "plekje", rit.pk, data={"volume_m3": 1, "opmerking": "PLEX"})
        self.post(self.piloot, "rit_status", rit.pk, "geannuleerd")
        self.assertEqual(set(Vraag.objects.values_list("status", "rit")), {("open", None)})
        self.assertTrue(Notification.objects.filter(user=self.vrager, title__contains="vervalt").exists())
        self.assertTrue(Notification.objects.filter(user=self.ander, title__contains="geen plek").exists())

    def test_vertrokken_houdt_toezeggingen(self):
        rit = self.rit()
        self.vraag_plekje(rit)
        vraag = Vraag.objects.get()
        self.post(self.piloot, "vraag_actie", vraag.pk, "accepteer")
        self.post(self.piloot, "rit_status", rit.pk, "vertrokken")
        vraag.refresh_from_db()
        self.assertEqual((vraag.status, vraag.rit), ("toegezegd", rit))


class TestLosseVraag(Basis):
    def test_vraag_op_bord_en_meenemen(self):
        r = self.post(self.vrager, "vraag_nieuw", data={"volume_m3": 40_000, "opmerking": "Ishtar"})
        self.assertEqual(r.status_code, 302)
        vraag = Vraag.objects.get()
        self.assertEqual(vraag.status, "open")

        self.post(self.vrager, "vraag_actie", vraag.pk, "meenemen")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "open", "eigen vraag zelf meenemen kan niet")

        self.post(self.piloot, "vraag_actie", vraag.pk, "meenemen")
        vraag.refresh_from_db()
        self.assertEqual((vraag.status, vraag.vervoerder), ("toegezegd", self.piloot))

        self.post(self.piloot, "vraag_actie", vraag.pk, "terugtrekken")
        vraag.refresh_from_db()
        self.assertEqual((vraag.status, vraag.vervoerder), ("open", None))

    def test_intrekken_meldt_vervoerder(self):
        vraag = Vraag.objects.create(aanvrager=self.vrager, volume_m3=5, status="toegezegd", vervoerder=self.piloot)
        self.post(self.vrager, "vraag_actie", vraag.pk, "annuleer")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "geannuleerd")
        self.assertTrue(Notification.objects.filter(user=self.piloot, title__contains="ingetrokken").exists())

    def test_oude_vraag_verdwijnt(self):
        oud = Vraag.objects.create(aanvrager=self.vrager, volume_m3=5)
        Vraag.objects.filter(pk=oud.pk).update(aangemaakt=timezone.now() - timedelta(days=40))
        self.assertFalse(Vraag.objects.zichtbaar().exists())
