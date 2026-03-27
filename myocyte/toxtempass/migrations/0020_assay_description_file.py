from django.db import migrations, models


class Migration(migrations.Migration):

    initial = False

    dependencies = [
        ("toxtempass", "0019_filedownloadlog_historicalfiledownloadlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="assay",
            name="description_file",
            field=models.CharField(
                max_length=500,
                blank=True,
                null=True,
                help_text="Path to the description file for this assay",
            ),
        ),
        migrations.AddField(
            model_name="assay",
            name="use_description_file",
            field=models.BooleanField(
                default=False,
                help_text="Whether to use the description file content instead of the description field",
            ),
        ),
    ]
