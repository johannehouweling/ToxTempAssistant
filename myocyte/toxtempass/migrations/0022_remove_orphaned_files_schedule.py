"""Remove stale django-q schedule for cleanup_orphaned_files.

The function toxtempass.utilities.cleanup_orphaned_files was removed but its
Schedule row remained in the database, causing the django-q worker to fail
repeatedly.
"""

from django.db import migrations


def remove_stale_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(func="toxtempass.utilities.cleanup_orphaned_files").delete()

    Failure = apps.get_model("django_q", "Failure")
    Failure.objects.filter(func="toxtempass.utilities.cleanup_orphaned_files").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("toxtempass", "0021_assay_created_by_study_created_by"),
        ("django_q", "__latest__"),
    ]

    operations = [
        migrations.RunPython(remove_stale_schedule, migrations.RunPython.noop),
    ]
