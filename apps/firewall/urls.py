from django.urls import path

from . import views

urlpatterns = [
    path("", views.firewall_index, name="firewall_index"),
    path("groups/add/", views.group_add, name="firewall_group_add"),
    path("groups/<str:name>/delete/", views.group_delete, name="firewall_group_delete"),
    path("<str:key>/panel/", views.firewall_panel, name="firewall_panel"),
    path("<str:key>/options/", views.options_save, name="firewall_options_save"),
    path("<str:key>/rules/add/", views.rule_add, name="firewall_rule_add"),
    path("<str:key>/rules/<int:pos>/edit/", views.rule_edit, name="firewall_rule_edit"),
    path("<str:key>/rules/<int:pos>/toggle/", views.rule_toggle, name="firewall_rule_toggle"),
    path("<str:key>/rules/<int:pos>/move/", views.rule_move, name="firewall_rule_move"),
    path("<str:key>/rules/<int:pos>/delete/", views.rule_delete, name="firewall_rule_delete"),
    path("<str:key>/aliases/add/", views.alias_add, name="firewall_alias_add"),
    path("<str:key>/aliases/<str:name>/delete/", views.alias_delete, name="firewall_alias_delete"),
    path("<str:key>/ipset/add/", views.ipset_add, name="firewall_ipset_add"),
    path("<str:key>/ipset/<str:name>/delete/", views.ipset_delete, name="firewall_ipset_delete"),
    path("<str:key>/ipset/<str:name>/entry/add/", views.ipset_entry_add, name="firewall_ipset_entry_add"),
    path("<str:key>/ipset/<str:name>/entry/remove/", views.ipset_entry_remove, name="firewall_ipset_entry_remove"),
]
