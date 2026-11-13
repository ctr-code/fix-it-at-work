"""
SLA targets become an amount and a unit (round-the-clock hours, working hours or working days), and a
Holiday table for days that aren't working days. Existing rules keep exactly the same targets, in
round-the-clock hours; `manage.py sync_sla` then sets the brief's table.
"""
from django.db import migrations, models


def hours_to_amounts(apps, schema_editor):
    SLARule = apps.get_model('cases', 'SLARule')
    for rule in SLARule.objects.all():
        rule.acknowledge_amount, rule.acknowledge_unit = rule.acknowledge_hours, 'hours'
        rule.resolve_amount, rule.resolve_unit = rule.resolve_hours, 'hours'
        rule.save(update_fields=['acknowledge_amount', 'acknowledge_unit', 'resolve_amount', 'resolve_unit'])


def amounts_to_hours(apps, schema_editor):
    """Going back: working time can't be turned into fixed hours exactly, so use a 9-hour working day."""
    SLARule = apps.get_model('cases', 'SLARule')
    per = {'hours': 1, 'working_hours': 1, 'working_days': 9}
    for rule in SLARule.objects.all():
        rule.acknowledge_hours = rule.acknowledge_amount * per[rule.acknowledge_unit]
        rule.resolve_hours = rule.resolve_amount * per[rule.resolve_unit]
        rule.save(update_fields=['acknowledge_hours', 'resolve_hours'])


UNITS = [('hours', 'hours (round the clock)'), ('working_hours', 'working hours'), ('working_days', 'working days')]


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0012_visit_media'),
    ]

    operations = [
        migrations.AddField('slarule', 'acknowledge_amount',
                            models.PositiveIntegerField(default=1, verbose_name='Respond within')),
        migrations.AddField('slarule', 'acknowledge_unit',
                            models.CharField(choices=UNITS, default='hours', max_length=15)),
        migrations.AddField('slarule', 'resolve_amount',
                            models.PositiveIntegerField(default=1, verbose_name='Resolve within')),
        migrations.AddField('slarule', 'resolve_unit',
                            models.CharField(choices=UNITS, default='working_days', max_length=15)),
        migrations.RunPython(hours_to_amounts, amounts_to_hours),
        migrations.RemoveField('slarule', 'acknowledge_hours'),
        migrations.RemoveField('slarule', 'resolve_hours'),
        migrations.AlterField('slarule', 'acknowledge_amount', models.PositiveIntegerField(verbose_name='Respond within')),
        migrations.AlterField('slarule', 'resolve_amount', models.PositiveIntegerField(verbose_name='Resolve within')),
        migrations.AlterModelOptions('slarule', {'verbose_name': 'SLA rule'}),
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True)),
                ('name', models.CharField(max_length=80)),
            ],
            options={'ordering': ['date']},
        ),
    ]
