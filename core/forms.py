from django import forms


class ProfileForm(forms.Form):
    """
    Form for editing ones email address on the profile page
    """
    email = forms.EmailField()
