"""
Data model for the Request to Resolution journey.

Follows Appendix A of the brief. Reporter details are kept on the Case to
keep the prototype simple (one form, no accounts needed to report).
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    REPORTER = 'reporter', 'Reporter'
    HANDLER = 'handler', 'Case handler'
    OFFICER = 'officer', 'Field officer'
    MANAGER = 'manager', 'Manager'


STAFF_ROLES = [Role.HANDLER, Role.MANAGER]


class Profile(models.Model):
    """Holds the user's role. Everyone who signs up starts as a Reporter."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.REPORTER)

    def __str__(self):
        return f'{self.user} ({self.get_role_display()})'


def get_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return Role.MANAGER
    profile = getattr(user, 'profile', None)
    return profile.role if profile else Role.REPORTER


class Priority(models.TextChoices):
    URGENT = 'urgent', 'Urgent'
    HIGH = 'high', 'High'
    MEDIUM = 'medium', 'Medium'
    LOW = 'low', 'Low'


PRIORITY_RANK = {'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}


class Status(models.TextChoices):
    NEW = 'new', 'New - awaiting triage'
    ASSIGNED = 'assigned', 'Assigned'
    IN_PROGRESS = 'in_progress', 'In progress - follow-up needed'
    RESOLVED = 'resolved', 'Resolved - reply being prepared'
    CLOSED = 'closed', 'Closed'
    DUPLICATE = 'duplicate', 'Merged as duplicate'


OPEN_STATUSES = [Status.NEW, Status.ASSIGNED, Status.IN_PROGRESS]


class Language(models.TextChoices):
    EN = 'en', 'English'
    PL = 'pl', 'Polski (Polish)'
    UR = 'ur', 'اردو (Urdu)'
    ES = 'es', 'Español (Spanish)'


class Team(models.Model):
    name = models.CharField(max_length=80, unique=True)
    contact_email = models.EmailField()
    working_hours = models.CharField(max_length=80, default='Mon-Fri 08:00-17:00')
    manager = models.CharField(max_length=80)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=200, blank=True)
    default_team = models.ForeignKey(Team, on_delete=models.PROTECT)
    default_priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    # Comma separated words used by the triage assistant
    keywords = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Officer(models.Model):
    name = models.CharField(max_length=80)
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='officers')
    contact_email = models.EmailField()
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='officer')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.team})'


class SLARule(models.Model):
    priority = models.CharField(max_length=10, choices=Priority.choices, unique=True)
    acknowledge_hours = models.PositiveIntegerField()
    resolve_working_days = models.PositiveIntegerField()

    def __str__(self):
        return f'{self.get_priority_display()}: ack {self.acknowledge_hours}h, resolve {self.resolve_working_days} working days'


def add_working_days(start, days):
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


class Case(models.Model):
    reference = models.CharField(max_length=12, unique=True, editable=False)

    # What the reporter tells us
    title = models.CharField('What is the problem?', max_length=120)
    description = models.TextField('Tell us more')
    building = models.CharField(max_length=80)
    location_detail = models.CharField('Floor / room / area', max_length=120, blank=True)
    reported_urgency = models.CharField(
        'How urgent is it?', max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    photo = models.FileField(upload_to='reports/', blank=True)
    reporter_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name='reported_cases')
    reporter_name = models.CharField('Your name', max_length=80)
    reporter_email = models.EmailField('Your email')
    preferred_language = models.CharField(max_length=5, choices=Language.choices, default=Language.EN)
    preferred_contact = models.CharField(
        max_length=10, choices=[('email', 'Email'), ('phone', 'Phone'), ('teams', 'Teams message')], default='email')

    # Decisions made by a person at triage
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    priority = models.CharField(max_length=10, choices=Priority.choices, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    assigned_team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL)
    assigned_officer = models.ForeignKey(Officer, null=True, blank=True, on_delete=models.SET_NULL)
    duplicate_of = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='duplicates')
    triaged_by = models.CharField(max_length=80, blank=True)
    ai_suggestion_accepted = models.BooleanField(null=True)

    # What the AI assistant suggested (kept for transparency and audit)
    ai_category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+')
    ai_priority = models.CharField(max_length=10, choices=Priority.choices, blank=True)
    ai_summary = models.TextField(blank=True)
    ai_reasoning = models.TextField(blank=True)
    ai_confidence = models.PositiveIntegerField(default=0)
    ai_duplicate_candidate = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                               related_name='+')

    # Timeline
    date_reported = models.DateTimeField(default=timezone.now)
    date_acknowledged = models.DateTimeField(null=True, blank=True)
    date_resolved = models.DateTimeField(null=True, blank=True)
    date_closed = models.DateTimeField(null=True, blank=True)
    sla_acknowledge_due = models.DateTimeField(null=True, blank=True)
    sla_due = models.DateTimeField('SLA due date', null=True, blank=True)
    first_time_fix = models.BooleanField(null=True)

    class Meta:
        ordering = ['-date_reported']

    def __str__(self):
        return f'{self.reference} {self.title}'

    def save(self, *args, **kwargs):
        if not self.reference:
            last = Case.objects.order_by('-reference').first()
            self.reference = f'FIW-{(int(last.reference[4:]) + 1 if last else 1):04d}'
        super().save(*args, **kwargs)

    def apply_sla(self):
        rule = SLARule.objects.filter(priority=self.priority).first()
        if rule:
            self.sla_acknowledge_due = self.date_reported + timedelta(hours=rule.acknowledge_hours)
            self.sla_due = add_working_days(self.date_reported, rule.resolve_working_days)

    @property
    def is_open(self):
        return self.status in OPEN_STATUSES

    @property
    def is_overdue(self):
        if not self.sla_due:
            return False
        end = self.date_resolved or timezone.now()
        return end > self.sla_due

    @property
    def stage(self):
        """Index 0-5 of the journey stage, for the progress tracker."""
        return {
            Status.NEW: 1, Status.ASSIGNED: 2, Status.IN_PROGRESS: 3,
            Status.RESOLVED: 4, Status.CLOSED: 5, Status.DUPLICATE: 5,
        }[self.status]


class SiteVisit(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='visits')
    officer = models.ForeignKey(Officer, on_delete=models.PROTECT)
    visited_at = models.DateTimeField(default=timezone.now)
    note = models.TextField('What did you find and do?')
    transcript_used = models.BooleanField(default=False)
    ai_summary = models.TextField(blank=True)
    photo = models.FileField(upload_to='visits/', blank=True)
    fixed = models.BooleanField('Issue fixed on this visit', default=False)

    class Meta:
        ordering = ['visited_at']


class Communication(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = 'receipt', 'Receipt (automatic)'
        ACKNOWLEDGEMENT = 'ack', 'Acknowledgement'
        OUTCOME = 'outcome', 'Outcome letter'

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='communications')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.EN)
    draft_text = models.TextField()
    ai_drafted = models.BooleanField(default=False)
    approved_by = models.CharField(max_length=80, blank=True)
    date_sent = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']
