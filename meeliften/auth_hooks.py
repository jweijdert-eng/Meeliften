"""Hook into Alliance Auth — Meeliften."""

from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from meeliften import urls


class MeeliftenMenuItem(MenuItemHook):
    """Menu-item met een badge voor plekje-aanvragen die op jouw antwoord wachten."""

    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("Meeliften"),
            "fas fa-shuttle-space fa-fw",
            "meeliften:index",
            navactive=["meeliften:"],
        )

    def render(self, request):
        if not request.user.has_perm("meeliften.basic_access"):
            return ""
        from meeliften.models import Vraag

        wacht = Vraag.objects.filter(rit__piloot=request.user, status=Vraag.Status.AANGEVRAAGD).count()
        self.count = wacht or None
        return MenuItemHook.render(self, request)


@hooks.register("menu_item_hook")
def register_menu():
    return MeeliftenMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "meeliften", r"^meeliften/")
