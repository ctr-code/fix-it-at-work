"""
Add the demo buildings from seed_demo, and fill in the address and map point of cases at those buildings
that don't have one yet, without deleting anything:

    python manage.py sync_buildings

Use it on a database that already has cases (instead of re-running seed_demo, which would delete them).
A location a reporter shared from their phone is never replaced.
"""
from django.core.management.base import BaseCommand

from cases.models import Case

from .seed_demo import sync_buildings


class Command(BaseCommand):
    help = 'Add the demo buildings and fill in missing case addresses and map points (keeps all cases)'

    def handle(self, *args, **options):
        added = sync_buildings()
        filled = 0
        for case in Case.objects.filter(latitude__isnull=True) | Case.objects.filter(address=''):
            before = (case.address, case.latitude, case.longitude)
            case.fill_location_from_building()
            if (case.address, case.latitude, case.longitude) != before:
                case.save(update_fields=['address', 'latitude', 'longitude', 'location_source'])
                filled += 1
        self.stdout.write(self.style.SUCCESS(
            f'Buildings: {added} added. Cases: {filled} given an address or map point.'))
