"""App URLs — Meeliften."""

from django.urls import path

from meeliften import views

app_name = "meeliften"

urlpatterns = [
    path("", views.index, name="index"),
    path("rit/nieuw/", views.rit_form, name="rit_nieuw"),
    path("rit/<int:rit_id>/bewerk/", views.rit_form, name="rit_bewerk"),
    path("rit/<int:rit_id>/status/<str:status>/", views.rit_status, name="rit_status"),
    path("rit/<int:rit_id>/plekje/", views.vraag_form, name="plekje"),
    path("vraag/nieuw/", views.vraag_form, name="vraag_nieuw"),
    path("vraag/<int:vraag_id>/<str:actie>/", views.vraag_actie, name="vraag_actie"),
]
