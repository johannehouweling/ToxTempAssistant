from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('toxtempass', '0027_assay_processing_log_user_alerts'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssayCost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model_key', models.CharField(help_text='Deployment key used, e.g. "1:GPT4O".', max_length=64)),
                ('model_id', models.CharField(blank=True, default='', help_text='Underlying model id at run time, e.g. "gpt-4o".', max_length=128)),
                ('input_tokens', models.PositiveBigIntegerField(default=0, help_text='Total prompt tokens consumed across all questions in this run.')),
                ('output_tokens', models.PositiveBigIntegerField(default=0, help_text='Total completion tokens produced across all questions in this run.')),
                ('cost_input_per_1m', models.DecimalField(blank=True, decimal_places=6, help_text='Snapshot of input price (USD / 1 M tokens) at run time.', max_digits=12, null=True)),
                ('cost_output_per_1m', models.DecimalField(blank=True, decimal_places=6, help_text='Snapshot of output price (USD / 1 M tokens) at run time.', max_digits=12, null=True)),
                ('cost_input', models.DecimalField(blank=True, decimal_places=6, help_text='Calculated input cost in USD for this run.', max_digits=12, null=True)),
                ('cost_output', models.DecimalField(blank=True, decimal_places=6, help_text='Calculated output cost in USD for this run.', max_digits=12, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assay', models.ForeignKey(help_text='The assay this cost record belongs to.', on_delete=django.db.models.deletion.CASCADE, related_name='costs', to='toxtempass.assay')),
            ],
            options={
                'verbose_name': 'Assay LLM Cost',
                'verbose_name_plural': 'Assay LLM Costs',
                'ordering': ['-updated_at'],
                'unique_together': {('assay', 'model_key')},
            },
        ),
    ]
