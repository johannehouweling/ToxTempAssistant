from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('toxtempass', '0028_assaycost'),
    ]

    operations = [
        migrations.AddField(
            model_name='assaycost',
            name='cost_unit',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Currency unit from the cost-unit tag at run time, e.g. "Eur".',
                max_length=16,
            ),
        ),
    ]
