# Generated by Django 5.1.6 on 2025-06-02 22:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('toxtempass', '0003_feedback_usefulness_rating'),
    ]

    operations = [
        migrations.AddField(
            model_name='assay',
            name='status',
            field=models.CharField(choices=[('none', 'None'), ('busy', 'Busy'), ('done', 'Done')], default='none', max_length=10),
        ),
    ]
