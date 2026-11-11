from django import forms

from .models import OPEN_STATUSES, Case, Category, Officer, Priority, Role, SiteVisit, Team


class SignupNameForm(forms.Form):
    """Extra fields on the allauth sign-up page. New accounts are always Reporters."""
    first_name = forms.CharField(max_length=80, label='First name')
    last_name = forms.CharField(max_length=80, label='Last name')
    field_order = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2']

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()


class ReportForm(forms.ModelForm):
    """Name and email come from the signed-in account, so they are not asked for here."""

    class Meta:
        model = Case
        labels = {'hs_risk': 'This could hurt someone'}
        fields = [
            'title', 'description', 'building', 'location_detail', 'reported_urgency', 'impact', 'hs_risk',
            'asset_tag', 'photo', 'preferred_language', 'preferred_contact',
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
            # No 'capture', so phones offer the camera or the photo library
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }
        help_texts = {
            'reported_urgency': 'Urgent = risk to people or property right now.',
            'hs_risk': 'Tick if someone could get hurt, for example water near electrics, a loose ceiling panel '
                       'or a trip hazard. We will make it safe first.',
            'asset_tag': 'Optional. The ID label on the equipment, if it has one.',
            'preferred_language': 'We will reply in this language.',
            'photo': 'Optional, but it helps us bring the right tools first time.',
        }

    def clean_asset_tag(self):
        return self.cleaned_data['asset_tag'].strip().upper()


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


class TriageForm(forms.Form):
    """Choose the team first. The category and officer lists only show options for that team."""
    team = forms.ModelChoiceField(Team.objects.order_by('name'))
    category = forms.ModelChoiceField(Category.objects.select_related('default_team'),
                                      help_text='Only categories handled by the chosen team are listed.')
    priority = forms.ChoiceField(choices=Priority.choices)
    officer = forms.ModelChoiceField(Officer.objects.select_related('team'), required=False,
                                     help_text='Leave blank to let the team pick it up.')
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
        data = super().clean()
        team, category, officer = data.get('team'), data.get('category'), data.get('officer')
        if data.get('duplicate_of'):
            return data  # merging a duplicate doesn't route the case anywhere
        if team and category and category.default_team_id != team.id:
            self.add_error('category', f'{category} is not handled by {team}. Choose one of its categories.')
        if team and officer and officer.team_id != team.id:
            self.add_error('officer', f'{officer.name} is not in {team}.')
        return data


class VisitForm(forms.ModelForm):
    transcript_used = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = SiteVisit
        fields = ['note', 'photo', 'fixed', 'transcript_used']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Type or tap "Dictate" and speak.'}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/*', 'capture': 'environment'}),
        }


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
