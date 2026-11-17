from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("exporter", "0003_lxcexportjob_lxcpximportjob"),
    ]

    operations = [
        migrations.AddField(
            model_name="exportjob",
            name="delete_after_download",
            field=models.BooleanField(
                default=False,
                help_text="Remove the package without asking as soon as one download has completed.",
            ),
        ),
        migrations.AddField(
            model_name="exportjob",
            name="downloaded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lxcexportjob",
            name="delete_after_download",
            field=models.BooleanField(
                default=False,
                help_text="Remove the package without asking as soon as one download has completed.",
            ),
        ),
        migrations.AddField(
            model_name="lxcexportjob",
            name="downloaded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
