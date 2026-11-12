from django import forms

from .models import (
    MAX_PHOTO_MB, MAX_REPORT_PHOTOS, OPEN_STATUSES, Case, Category, Officer, Priority, Role, SiteVisit, Team,
)


class SignupNameForm(forms.Form):
    """Extra fields on the allauth sign-up page. New accounts are always Reporters."""
    first_name = forms.CharField(max_length=80, label='First name')
    last_name = forms.CharField(max_length=80, label='Last name')
    field_order = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2']

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()


PHOTO_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')
PHOTO_TYPES = ('image/jpeg', 'image/png', 'image/webp')


class MultipleFileInput(forms.ClearableFileInput):
    """A file input that lets people choose several files at once."""
    allow_multiple_selected = True


class PhotosField(forms.FileField):
    """Several optional photos, cleaned into a list (empty when none are chosen)."""
    max_files = MAX_REPORT_PHOTOS
    max_mb = MAX_PHOTO_MB

    def __init__(self, **kwargs):
        # No 'capture', so phones offer the camera or the photo library
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': ','.join(PHOTO_TYPES)}))
        super().__init__(**kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(PhotosField, self).clean(f, initial) for f in files if f]


class ReportForm(forms.ModelForm):
    """Name and email come from the signed-in account, so they are not asked for here.
    Photos are saved separately as ReportPhoto rows (see the report view)."""

    photo = PhotosField(required=False, label='Photos',
                        help_text='Optional, but it helps us bring the right tools first time.')

    class Meta:
        model = Case
        labels = {'hs_risk': 'This could hurt someone'}
        fields = [
            'title', 'description', 'building', 'location_detail', 'reported_urgency', 'impact', 'hs_risk',
            'asset_tag', 'preferred_language', 'preferred_contact',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Water leaking from ceiling'}),
            'description': forms.Textarea(attrs={
                'rows': 4, 'placeholder': 'What is happening, since when, and is anyone affected? '
                                          'You can write in any language.'}),
            'building': forms.TextInput(attrs={'placeholder': 'e.g. Main Office', 'list': 'buildings'}),
            'location_detail': forms.TextInput(attrs={'placeholder': 'e.g. 2nd floor, kitchen'}),
            'reported_urgency': forms.RadioSelect,
            'impact': forms.RadioSelect,
            'asset_tag': forms.TextInput(attrs={'placeholder': 'e.g. PRN-B2-01', 'autocapitalize': 'characters'}),
        }
        help_texts = {
            'reported_urgency': 'Urgent = risk to people or property right now.',
            'hs_risk': 'Tick if someone could get hurt, for example water near electrics, a loose ceiling panel '
                       'or a trip hazard. We will make it safe first.',
            'asset_tag': 'Optional. The ID label on the equipment, if it has one.',
            'preferred_language': 'We will reply in this language.',
        }

    def clean_asset_tag(self):
        return self.cleaned_data['asset_tag'].strip().upper()

    def clean_photo(self):
        return check_photos(self.cleaned_data.get('photo'))


def check_photos(photos):
    """The same limits the upload area checks in the browser, enforced on the server:
    how many photos, which file types and how big. Returns the list of photos."""
    photos = photos or []
    if len(photos) > MAX_REPORT_PHOTOS:
        raise forms.ValidationError(
            f'Please choose up to {MAX_REPORT_PHOTOS} photos. You chose {len(photos)}.')
    problems = []
    for f in photos:
        name = f.name or 'A file'
        if not name.lower().endswith(PHOTO_EXTENSIONS) or (f.content_type and f.content_type not in PHOTO_TYPES):
            problems.append(f'{name} is not a JPG, PNG or WEBP image.')
        elif f.size > MAX_PHOTO_MB * 1024 * 1024:
            problems.append(f'{name} is {f.size / (1024 * 1024):.1f}MB. Each photo must be {MAX_PHOTO_MB}MB or less.')
    if problems:
        raise forms.ValidationError(problems)
    return photos


class ReportUpdateForm(forms.Form):
    """More details and photos the reporter adds to their report after sending it."""
    text = forms.CharField(
        label='What else should we know?', required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'For example: it has got worse, it now affects '
                                                                'the whole floor, or a better description of where it is.'}))
    photo = PhotosField(required=False, label='Photos',
                        help_text='Optional. Extra photos help the officer bring the right tools.')

    def clean_photo(self):
        return check_photos(self.cleaned_data.get('photo'))

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get('text') or '').strip() and not cleaned.get('photo') and not self.errors:
            raise forms.ValidationError('Add some details or at least one photo.')
        return cleaned


class FeedbackForm(forms.ModelForm):
    """The reporter's rating of a closed case."""

    class Meta:
        model = Case
        fields = ['satisfaction', 'satisfaction_comments']
        labels = {
            'satisfaction': 'How happy are you with how this was handled?',
            'satisfaction_comments': 'Anything you would like to tell us? (optional)',
        }
        widgets = {
            'satisfaction': forms.RadioSelect,
            'satisfaction_comments': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['satisfaction'].required = True
        # Drop Django's empty "---------" option from the radio buttons
        self.fields['satisfaction'].choices = [c for c in self.fields['satisfaction'].choices if c[0] != '']


class RoutingForm(forms.Form):
    """Where a case goes: choose the team first. The category and officer lists only show options for that team."""
    team = forms.ModelChoiceField(Team.objects.order_by('name'))
    category = forms.ModelChoiceField(Category.objects.select_related('default_team'),
                                      help_text='Only categories handled by the chosen team are listed.')
    priority = forms.ChoiceField(choices=Priority.choices)
    officer = forms.ModelChoiceField(Officer.objects.select_related('team'), required=False,
                                     help_text='Leave blank to let the team pick it up.')

    def clean(self):
        data = super().clean()
        team, category, officer = data.get('team'), data.get('category'), data.get('officer')
        if team and category and category.default_team_id != team.id:
            self.add_error('category', f'{category} is not handled by {team}. Choose one of its categories.')
        if team and officer and officer.team_id != team.id:
            self.add_error('officer', f'{officer.name} is not in {team}.')
        return data


class TriageForm(RoutingForm):
    duplicate_of = forms.ModelChoiceField(
        Case.objects.none(), required=False,
        help_text='If this is the same issue as an open case, merge it.')

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Case.objects.filter(status__in=OPEN_STATUSES)
        if case:
            qs = qs.exclude(pk=case.pk)
        self.fields['duplicate_of'].queryset = qs

    def clean(self):
        if self.cleaned_data.get('duplicate_of'):
            return self.cleaned_data  # merging a duplicate doesn't route the case anywhere
        return super().clean()


class ReassignForm(RoutingForm):
    """Change the priority, team, category or officer of a case that has already been triaged."""
    reason = forms.CharField(
        max_length=200, required=False, label='Reason for the change (optional)',
        help_text='Shown in the case history, e.g. "Water now reaching the server room".')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['officer'].empty_label = 'Unassigned - the team picks it up'


class VisitForm(forms.ModelForm):
    transcript_used = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = SiteVisit
        fields = ['note', 'action', 'photo', 'fixed', 'transcript_used']
        widgets = {
            'note': forms.Textarea(attrs={
                'rows': 3, 'placeholder': 'What was wrong when you got there? Type, or tap "Dictate" and speak.'}),
            'action': forms.Textarea(attrs={
                'rows': 3, 'placeholder': 'What did you repair, replace, test or arrange?'}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/*', 'capture': 'environment'}),
        }
        help_texts = {'action': 'This goes into the letter that tells the reporter what was done.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Older visits may have no action, but every new visit must say what was done
        self.fields['action'].required = True


class LetterForm(forms.Form):
    draft_text = forms.CharField(label='Letter (edit before approving)', widget=forms.Textarea(attrs={'rows': 12}))


class RoleForm(forms.Form):
    """Used by managers to change someone's role. Field officers also need a team."""
    role = forms.ChoiceField(choices=Role.choices)
    team = forms.ModelChoiceField(Team.objects.all(), required=False)

    def clean(self):
        data = super().clean()
        if data.get('role') == Role.OFFICER and not data.get('team'):
            self.add_error('team', 'Choose a team for a field officer.')
        return data
