from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_mfaconfig_allow_email_recovery"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="ui_theme",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
