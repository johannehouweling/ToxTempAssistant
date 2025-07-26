# toxtempass/migrations/0006_backfill_initial_questionset.py
from django.db import migrations

def create_initial_questionset(apps, schema_editor):
    QuestionSet = apps.get_model("toxtempass", "QuestionSet")
    Section     = apps.get_model("toxtempass", "Section")
    Person      = apps.get_model("toxtempass", "Person")

    # pick a sane default for created_by—e.g. the first superuser, or id=1
    admin = Person.objects.filter(is_superuser=True).first()
    initial = QuestionSet.objects.create(
        label="v1",
        display_name="2019 original",
        created_by=admin,
    )

    # assign *every* existing Section to that QuestionSet
    Section.objects.all().update(question_set=initial)


class Migration(migrations.Migration):

    dependencies = [
        ("toxtempass", "0005_create_questionset_nullable"),
    ]

    operations = [
        migrations.RunPython(create_initial_questionset, reverse_code=migrations.RunPython.noop),
    ]