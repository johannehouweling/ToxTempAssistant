from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('toxtempass', '0026_alter_answer_files'),
    ]

    operations = [
        migrations.RenameField(
            model_name='assay',
            old_name='status_context',
            new_name='processing_log',
        ),
        migrations.AlterField(
            model_name='assay',
            name='processing_log',
            field=models.TextField(
                blank=True,
                default='',
                help_text=(
                    'Internal append-only log of file-processing and LLM events for '
                    'this assay (correlation ids, exception traces, info notices). '
                    'May contain debug-grade detail and is NOT shown to end users.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='assay',
            name='user_alerts',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'User-visible alerts rendered as dismissable banners on the assay '
                    'page. List of {message, level, ts} entries. Only pre-vetted '
                    'messages should be added — never raw exception text.'
                ),
            ),
        ),
    ]
