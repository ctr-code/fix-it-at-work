"""
Set the SLA rules to the brief's table (from seed_demo) and add the bank holidays, without deleting anything:

    python manage.py sync_sla
    python manage.py sync_sla --recalculate

--recalculate also works out every triaged case's response and resolution due dates again from the new rules,
counted from when it was reported. Without it, existing cases keep the due dates they were given.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from cases.models import OPEN_STATUSES, Case, Holiday, SLARule

from .seed_demo import sync_sla


class Command(BaseCommand):
    help = "Set the SLA rules to the brief's working-day targets and add bank holidays (keeps all cases)"

    def add_arguments(self, parser):
        parser.add_argument('--recalculate', action='store_true',
                            help="Also recalculate existing cases' due dates from the new rules")

    def handle(self, *args, **options):
        changed, added = sync_sla()
        self.stdout.write(self.style.SUCCESS(f'SLA rules: {changed} changed. Holidays: {added} added.'))
        for rule in SLARule.objects.order_by('-acknowledge_amount'):
            self.stdout.write(f'  {rule}')
        if not options['recalculate']:
            self.stdout.write('Existing cases keep their due dates (use --recalculate to update them).')
            return

        now = timezone.now()
        open_cases = Case.objects.filter(status__in=OPEN_STATUSES)
        before = open_cases.filter(sla_due__lt=now).count()
        holidays = set(Holiday.objects.values_list('date', flat=True))
        rules = {r.priority: r for r in SLARule.objects.all()}
        updated = 0
        for case in Case.objects.exclude(priority='').exclude(sla_due=None):
            rule = rules.get(case.priority)
            if rule is None:
                continue
            case.sla_acknowledge_due = rule.acknowledge_due(case.date_reported, holidays)
            case.sla_due = rule.resolve_due(case.date_reported, holidays)
            case.save(update_fields=['sla_acknowledge_due', 'sla_due'])
            updated += 1
        after = open_cases.filter(sla_due__lt=now).count()
        self.stdout.write(self.style.SUCCESS(
            f'Due dates recalculated for {updated} cases. Open cases past their due date: {before} before, {after} now.'))
