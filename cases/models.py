"""
Data model for the Request to Resolution journey.

Follows Appendix A of the brief. Reporter details are kept on the Case to
keep the prototype simple (one form, no accounts needed to report).
"""
from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
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


class Impact(models.TextChoices):
    """How many people the issue affects, as reported."""
    SINGLE_USER = 'single_user', 'Just me'
    TEAM = 'team', 'My team'
    DEPARTMENT = 'department', 'My department'
    BUILDING_WIDE = 'building_wide', 'The whole building'


# Reporters can give or change feedback for this long after their case is closed
FEEDBACK_WINDOW = timedelta(days=14)
# Scores of 2 or less are shown to case handlers for this long after closing, so they can follow up
UNHAPPY_SCORE = 2
UNHAPPY_FOLLOW_UP = FEEDBACK_WINDOW + timedelta(days=14)

SATISFACTION_CHOICES = [(5, '5 - Very satisfied'), (4, '4 - Satisfied'), (3, '3 - Neither'),
                        (2, '2 - Dissatisfied'), (1, '1 - Very dissatisfied')]


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


class Building(models.Model):
    """One of the organisation's sites. When a report names it, the case gets its address and map point,
    so reporters don't have to type an address. Managed in the admin; see the sync_buildings command."""
    name = models.CharField(max_length=80, unique=True)
    address = models.CharField(max_length=200)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SLARule(models.Model):
    """
    Response and resolution targets for one priority, in calendar hours (the clock runs 24/7,
    including evenings and weekends), as on the mock data's SLA Settings sheet.
    """
    priority = models.CharField(max_length=10, choices=Priority.choices, unique=True)
    acknowledge_hours = models.PositiveIntegerField('Response target (hours)')
    resolve_hours = models.PositiveIntegerField('Resolution target (hours)')

    def __str__(self):
        return f'{self.get_priority_display()}: respond in {self.acknowledge_hours}h, resolve in {self.resolve_hours}h'


class Case(models.Model):
    # TKT-<year reported>-<4-digit number>, restarting at 0001 each year, e.g. TKT-2026-0042
    reference = models.CharField(max_length=13, unique=True, editable=False)

    # What the reporter tells us
    title = models.CharField('What is the problem?', max_length=120)
    description = models.TextField('Tell us more')
    building = models.CharField(max_length=80)
    location_detail = models.CharField('Floor / room / area', max_length=120, blank=True)
    # Where it is on a map: from the building directory, or from the reporter's phone if they chose to share it
    address = models.CharField('Street address', max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_source = models.CharField(max_length=10, blank=True, choices=[
        ('device', "Reporter's phone or computer"), ('map', 'Pinned on a map by the reporter'),
        ('building', 'Building address')])
    reported_urgency = models.CharField(
        'How urgent is it?', max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    impact = models.CharField('Who is affected?', max_length=15, choices=Impact.choices, default=Impact.SINGLE_USER)
    hs_risk = models.BooleanField('Health and safety risk', default=False)
    asset_tag = models.CharField(max_length=20, blank=True)
    # Older reports kept their single photo here. New reports store theirs as ReportPhoto (see all_photos).
    photo = models.FileField(upload_to='reports/', blank=True)
    reporter_user =models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
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

    # Reporter's feedback once the case is closed
    satisfaction = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=SATISFACTION_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    satisfaction_comments = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_reported']

    def __str__(self):
        return f'{self.reference} {self.title}'

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = f'TKT-{self.date_reported.year}-'
            last = Case.objects.filter(reference__startswith=prefix).order_by('-reference').first()
            self.reference = f'{prefix}{(int(last.reference[-4:]) + 1 if last else 1):04d}'
        super().save(*args, **kwargs)

    def apply_sla(self):
        rule = SLARule.objects.filter(priority=self.priority).first()
        if rule:
            self.sla_acknowledge_due = self.date_reported + timedelta(hours=rule.acknowledge_hours)
            self.sla_due = self.date_reported + timedelta(hours=rule.resolve_hours)

    @property
    def feedback_deadline(self):
        """Last moment the reporter can give or change feedback: 14 days after closing."""
        if self.status != Status.CLOSED or not self.date_closed:
            return None
        return self.date_closed + FEEDBACK_WINDOW

    @property
    def feedback_open(self):
        deadline = self.feedback_deadline
        return deadline is not None and timezone.now() <= deadline

    def can_give_feedback(self, user):
        """Only the person who reported it, and only while the feedback window is open."""
        return user.is_authenticated and self.reporter_user_id == user.id and self.feedback_open

    def can_add_details(self, user):
        """The person who reported it can add details and photos until the case is closed or merged."""
        return (user.is_authenticated and self.reporter_user_id == user.id
                and self.status not in (Status.CLOSED, Status.DUPLICATE))

    @property
    def has_map_point(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def map_url(self):
        """A link to the point on OpenStreetMap. Nothing is sent there unless someone opens the link."""
        if not self.has_map_point:
            return ''
        return (f'https://www.openstreetmap.org/?mlat={self.latitude}&mlon={self.longitude}'
                f'#map=18/{self.latitude}/{self.longitude}')

    def fill_location_from_building(self):
        """Use the building directory for anything the reporter didn't give: the address, and the map point
        unless they shared their own."""
        site = Building.objects.filter(name__iexact=self.building.strip()).first() if self.building else None
        if site is None:
            return
        if not self.address:
            self.address = site.address
        if not self.has_map_point and site.latitude is not None and site.longitude is not None:
            self.latitude, self.longitude = site.latitude, site.longitude
            self.location_source = 'building'

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

    def all_photos(self):
        """The photos sent with the report: an older report's single photo, then any newer ones.
        Photos added later with an update are shown with that update (see ReportUpdate)."""
        files = [self.photo] if self.photo else []
        return files + [p.image for p in self.photos.all() if p.update_id is None]


# Limits for photos attached to a report, shared by the form and the upload area
MAX_REPORT_PHOTOS = 5
MAX_PHOTO_MB = 10


class ReportUpdate(models.Model):
    """More details the reporter added after sending the report, with any extra photos."""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='updates')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='+')
    text = models.TextField('What else should we know?', blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at', 'pk']

    def __str__(self):
        return f'Update to {self.case.reference}'


class ReportPhoto(models.Model):
    """A photo the reporter attached to a report (up to MAX_REPORT_PHOTOS at a time), either with the
    report itself or with a later update."""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='photos')
    update = models.ForeignKey(ReportUpdate, null=True, blank=True, on_delete=models.CASCADE,
                               related_name='photos')
    image = models.FileField(upload_to='reports/')
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['uploaded_at', 'pk']

    def __str__(self):
        return f'Photo for {self.case.reference}'


class CaseChange(models.Model):
    """A change a case handler or manager made to an open case after triage (priority, team, category or
    officer), kept so everyone can see who changed what and why."""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='changes')
    changed_by = models.CharField(max_length=80)
    changed_at = models.DateTimeField(default=timezone.now)
    summary = models.TextField()  # one line per field, e.g. "Priority: Medium → High"
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-changed_at', '-pk']

    def __str__(self):
        return f'Change to {self.case.reference}'

    def lines(self):
        return self.summary.splitlines()


class Alert(models.Model):
    """An email telling a team (and its officer) about a case sent to them, kept so staff can see who was
    told what and when. Written by cases/alerts.py."""
    class Kind(models.TextChoices):
        ROUTED = 'routed', 'New job'
        CHANGED = 'changed', 'Job changed'

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='alerts')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    recipients = models.TextField()  # comma separated email addresses
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(default=timezone.now)
    delivered = models.BooleanField(default=False)
    error = models.CharField(max_length=200, blank=True)
    # Who it was for, so it shows on their Alerts page: the team's inbox (seen by every officer in the
    # team) and any officers it was addressed to by name
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name='alerts')
    officers = models.ManyToManyField(Officer, blank=True, related_name='alerts')

    class Meta:
        ordering = ['-sent_at', '-pk']

    def __str__(self):
        return f'{self.get_kind_display()} alert for {self.case.reference}'

    @classmethod
    def for_officer(cls, officer):
        """Alerts sent to this officer by name or to their team's inbox."""
        return cls.objects.filter(models.Q(team=officer.team_id) | models.Q(officers=officer)).distinct()


class AlertRead(models.Model):
    """One person has read one alert. Kept per person, because a team alert is shared by everyone in the team."""
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='reads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['alert', 'user'], name='one_read_per_person')]


class SiteVisit(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='visits')
    officer = models.ForeignKey(Officer, on_delete=models.PROTECT)
    visited_at = models.DateTimeField(default=timezone.now)
    # What the officer found, and what they did about it. Visits recorded before the two were split
    # have everything in note and a blank action.
    note = models.TextField('What did you find?')
    action = models.TextField('What did you do?', blank=True)
    transcript_used = models.BooleanField(default=False)
    ai_summary = models.TextField(blank=True)
    photo = models.FileField(upload_to='visits/', blank=True)
    fixed = models.BooleanField('Issue fixed on this visit', default=False)

    class Meta:
        ordering = ['visited_at']


class Communication(models.Model):
    """A message to the reporter. It counts as sent once date_sent is set (an outcome letter waits as a
    draft until a handler approves it), and as read once the reporter opens the report (read_at)."""
    class Kind(models.TextChoices):
        RECEIPT = 'receipt', 'Receipt (automatic)'
        ACKNOWLEDGEMENT = 'ack', 'Acknowledgement'
        UPDATE = 'update', 'Progress update'
        OUTCOME = 'outcome', 'Outcome letter'

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='communications')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.EN)
    draft_text = models.TextField()
    ai_drafted = models.BooleanField(default=False)
    approved_by = models.CharField(max_length=80, blank=True)
    date_sent = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']
