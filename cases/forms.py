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
        fields = [
            'title', 'description', 'building', 'location_detail', 'reported_urgency', 'photo',
            'preferred_language', 'preferred_contact',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Water leaking from ceiling'}),
            'description': forms.Textarea(attrs={
                'rows': 4, 'placeholder': 'What is happening, since when, and is anyone affected? '
                                          'You can write in any language.'}),
            'building': forms.TextInput(attrs={'placeholder': 'e.g. Main Office', 'list': 'buildings'}),
            'location_detail': forms.TextInput(attrs={'placeholder': 'e.g. 2nd floor, kitchen'}),
            'reported_urgency': forms.RadioSelect,
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/*', 'capture': 'environment'}),
        }
        help_texts = {
            'reported_urgency': 'Urgent = risk to people or property right now.',
            'preferred_language': 'We will reply in this language.',
            'photo': 'Optional, but it helps us bring the right tools first time.',
        }


class TriageForm(forms.Form):
    category = forms.ModelChoiceField(Category.objects.all())
    priority = forms.ChoiceField(choices=Priority.choices)
    team = forms.ModelChoiceField(Team.objects.all())
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
