"""Meeliften: het hele bord via de testclient. Draaien vanuit myauth/:
manage.py test meeliften --keepdb --noinput"""

from datetime import timedelta
from unittest.mock import patch

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
        data = dict(piloot=self.piloot, schip_type="jf", van="1DQ1-A", naar="Jita",
                    vertrek=timezone.now() + timedelta(hours=3), vrij_m3=300_000, vrij_schepen=None)
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
        Vraag.objects.create(aanvrager=self.vrager, van="Jita", naar="Q-02UL", wat="Ishtar", schepen=1)
        r = client(self.ander).get(reverse("meeliften:index"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "1DQ1-A")
        self.assertContains(r, "Ishtar")
        self.assertContains(r, "300.000")

    def test_formulieren_laden(self):
        rit = self.rit()
        for naam, args in (("rit_nieuw", []), ("vraag_nieuw", []), ("plekje", [rit.pk]), ("rit_bewerk", [rit.pk])):
            user = self.vrager if naam == "plekje" else self.piloot
            self.assertEqual(client(user).get(reverse(f"meeliften:{naam}", args=args)).status_code, 200, naam)

    def test_ander_mag_rit_niet_bewerken(self):
        rit = self.rit()
        self.assertEqual(client(self.ander).get(reverse("meeliften:rit_bewerk", args=[rit.pk])).status_code, 403)
        self.assertEqual(self.post(self.ander, "rit_status", rit.pk, "geannuleerd").status_code, 403)
        self.assertEqual(client(self.beheer).get(reverse("meeliften:rit_bewerk", args=[rit.pk])).status_code, 200)


class TestRit(Basis):
    def test_rit_aanbieden(self):
        r = self.post(self.piloot, "rit_nieuw", data={
            "character": self.piloot.profile.main_character.pk, "schip_type": "carrier", "schip_naam": "Thanatos",
            "van": "Q-02UL", "naar": "1DQ1-A", "vrij_schepen": 3,
        })
        self.assertEqual(r.status_code, 302)
        rit = Rit.objects.get()
        self.assertEqual((rit.piloot, rit.vrij_schepen, rit.vrij_m3), (self.piloot, 3, None))

    def test_rit_zonder_ruimte_geweigerd(self):
        r = self.post(self.piloot, "rit_nieuw", data={"schip_type": "jf", "van": "A", "naar": "B"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Rit.objects.exists())

    def test_van_is_naar_geweigerd(self):
        self.post(self.piloot, "rit_nieuw", data={"schip_type": "jf", "van": "Jita", "naar": "jita", "vrij_m3": 5})
        self.assertFalse(Rit.objects.exists())

    def test_standaard_icoon_per_klasse(self):
        self.assertIn("/types/28850/", self.rit().icoon)
        self.assertIn("/types/11567/", self.rit(schip_type="titan").icoon)
        self.assertEqual(self.rit(schip_type="anders").icoon, "")

    def test_herkend_schip_geeft_eigen_icoon_en_klasse(self):
        with patch("meeliften.forms.herken", return_value=(23913, "super")):
            self.post(self.piloot, "rit_nieuw", data={
                "schip_type": "carrier", "schip_naam": "Nyx", "van": "A", "naar": "B", "vrij_schepen": 2,
            })
        rit = Rit.objects.get()
        self.assertEqual((rit.schip_type, rit.schip_type_id), ("super", 23913))
        self.assertIn("/types/23913/", rit.icoon)

    def test_oude_ritten_verdwijnen(self):
        self.rit(vertrek=timezone.now() - timedelta(days=2))
        oud = self.rit(vertrek=None)
        Rit.objects.filter(pk=oud.pk).update(aangemaakt=timezone.now() - timedelta(days=20))
        vers = self.rit(vertrek=None)
        self.assertEqual(list(Rit.objects.zichtbaar()), [vers])


class TestPlekje(Basis):
    def vraag_plekje(self, rit, **kw):
        data = {"wat": "Muninn + ammo", "volume_m3": 50_000, "schepen": 0}
        data.update(kw)
        return self.post(self.vrager, "plekje", rit.pk, data=data)

    def test_vragen_accepteren_afleveren(self):
        rit = self.rit()
        self.assertEqual(self.vraag_plekje(rit).status_code, 302)
        vraag = Vraag.objects.get()
        self.assertEqual((vraag.status, vraag.rit, vraag.van, vraag.naar), ("aangevraagd", rit, "1DQ1-A", "Jita"))
        self.assertTrue(Notification.objects.filter(user=self.piloot, title__contains="plekje").exists())

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

    def test_schip_in_rit_zonder_smb_geweigerd(self):
        rit = self.rit()
        self.vraag_plekje(rit, volume_m3="", schepen=1)
        self.assertFalse(Vraag.objects.exists())

    def test_eigen_rit_geen_plekje(self):
        rit = self.rit()
        self.post(self.piloot, "plekje", rit.pk, data={"wat": "x", "volume_m3": 1, "schepen": 0})
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
        self.post(self.ander, "plekje", rit.pk, data={"wat": "PLEX", "volume_m3": 1, "schepen": 0})
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
        r = self.post(self.vrager, "vraag_nieuw", data={"van": "Jita", "naar": "Q-02UL", "wat": "Ishtar", "schepen": 1})
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
        vraag = Vraag.objects.create(aanvrager=self.vrager, van="A", naar="B", wat="x", volume_m3=5,
                                     status="toegezegd", vervoerder=self.piloot)
        self.post(self.vrager, "vraag_actie", vraag.pk, "annuleer")
        vraag.refresh_from_db()
        self.assertEqual(vraag.status, "geannuleerd")
        self.assertTrue(Notification.objects.filter(user=self.piloot, title__contains="ingetrokken").exists())

    def test_verlopen_vraag_verdwijnt(self):
        Vraag.objects.create(aanvrager=self.vrager, van="A", naar="B", wat="x", volume_m3=5,
                             uiterlijk=timezone.now().date() - timedelta(days=1))
        self.assertFalse(Vraag.objects.zichtbaar().exists())

    def test_systemen_zoeken(self):
        r = client(self.vrager).get(reverse("meeliften:systemen"), {"q": "J"})
        self.assertEqual(r.json(), {"systemen": []})
        r = client(self.vrager).get(reverse("meeliften:systemen"), {"q": "Jit"})
        self.assertEqual(r.status_code, 200)
