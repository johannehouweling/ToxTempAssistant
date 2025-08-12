# toxtempass/migrations/0007_make_questionset_and_section_non_nullable.py
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("toxtempass", "0006_backfill_initial_questionset"),
    ]

    operations = [
        migrations.AlterField(
            model_name="questionset",
            name="label",
            field=models.CharField(max_length=50, unique=True, null=False),
        ),
        migrations.AlterField(
            model_name="questionset",
            name="display_name",
            field=models.CharField(max_length=100, null=False),
        ),
        migrations.AlterField(
            model_name="questionset",
            name="created_by",
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="questionsets",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="section",
            name="question_set",
            field=models.ForeignKey(
                to="toxtempass.QuestionSet",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sections",
                null=False,
            ),
        ),
    ]
