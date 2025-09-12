# toxtempass/migrations/0005_create_questionset_nullable.py
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("toxtempass", "0004_assay_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestionSet",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("label", models.CharField(max_length=50, unique=True, null=True)),
                ("display_name", models.CharField(max_length=100, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="questionsets",
                    null=True,
                )),
            ],
        ),
        migrations.AddField(
            model_name="section",
            name="question_set",
            field=models.ForeignKey(
                to="toxtempass.QuestionSet",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sections",
                null=True,
                blank=True,
            ),
        ),
    ]
