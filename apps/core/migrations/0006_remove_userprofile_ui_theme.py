from django.db import migrations


class Migration(migrations.Migration):
    """Nexus redesign: a single theme, nothing saved per user."""

    dependencies = [
        ("core", "0005_userprofile_ui_theme"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userprofile",
            name="ui_theme",
        ),
    ]
