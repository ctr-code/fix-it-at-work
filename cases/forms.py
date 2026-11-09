from django import forms

from .models import Case, Category, Officer, Priority, SiteVisit, Team


class ReportForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = [
            'title', 'description', 'building', 'location_detail', 'reported_urgency', 'photo',
            'reporter_name', 'reporter_email', 'preferred_language', 'preferred_contact',
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
    triaged_by = forms.CharField(label='Your name (approver)', max_length=80)

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import OPEN_STATUSES
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
    approved_by = forms.CharField(label='Approved by', max_length=80)
