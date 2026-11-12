"""
Update the categories already in the database to match the lists in seed_demo, without
touching any cases:

    python manage.py sync_categories

Use it after changing CATEGORIES (for example adding triage keywords) instead of re-running
seed_demo, which would delete every case.
"""
from django.core.management.base import BaseCommand

from cases.models import Category, Team

from .seed_demo import CATEGORIES


class Command(BaseCommand):
    help = "Update category keywords and default priorities from seed_demo (keeps all cases)"

    def handle(self, *args, **options):
        updated = added = skipped = 0
        for name, team_name, priority, keywords in CATEGORIES:
            cat = Category.objects.filter(name=name).first()
            if cat:
                if (cat.keywords, cat.default_priority) != (keywords, priority):
                    cat.keywords, cat.default_priority = keywords, priority
                    cat.save(update_fields=['keywords', 'default_priority'])
                    updated += 1
                continue
            team = Team.objects.filter(name=team_name).first()
            if team is None:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'Skipped {name}: team "{team_name}" does not exist.'))
                continue
            Category.objects.create(name=name, default_team=team, default_priority=priority, keywords=keywords)
            added += 1
        self.stdout.write(self.style.SUCCESS(
            f'Categories: {updated} updated, {added} added, {skipped} skipped. Cases were not changed.'))
