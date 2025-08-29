from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django import forms as dj_forms
from .models import Profile
from django.contrib.auth import password_validation

class AudioUploadForm(forms.Form):
    LLM_CHOICES = [
        ('openai', 'OpenAI (GPT-4o-mini)'),
        ('gemini', 'Google Gemini (2.5-flash-lite)'),
        ('bedrock', 'AWS Bedrock (Nova Lite)'),
    ]
    
    llm_provider = forms.ChoiceField(choices=LLM_CHOICES, initial='gemini', widget=forms.Select(attrs={'style': 'width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem;'}))
    audio_file = forms.FileField(required=False)
    text_input = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'placeholder': 'Enter your Japanese text here for AI feedback...&#10;&#10;Example: 私は昨日映画を見ました。'
            }
        )
    )
    
    def clean(self):
        cleaned_data = super().clean()
        audio_file = cleaned_data.get('audio_file')
        text_input = cleaned_data.get('text_input')
        
        if not audio_file and not text_input:
            raise forms.ValidationError('Please provide either an audio file or text input.')
        
        return cleaned_data


User = get_user_model()

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]
        widgets = {
            "username": forms.TextInput(attrs={"style": "width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 6px;"}),
            "first_name": forms.TextInput(attrs={"style": "width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 6px;"}),
            "last_name": forms.TextInput(attrs={"style": "width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 6px;"}),
            "email": forms.EmailInput(attrs={"style": "width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 6px;"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get("instance")
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data.get("username")
        qs = User.objects.filter(username=username)
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username


class ProfileAvatarForm(forms.ModelForm):
    remove_avatar = forms.BooleanField(required=False, help_text="Remove current avatar")

    class Meta:
        model = Profile
        fields = ["avatar"]
        widgets = {
            "avatar": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.cleaned_data.get("remove_avatar"):
            profile.avatar = None
        if commit:
            profile.save()
        return profile


class PasswordUpdateForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "class": "input", "placeholder": "••••••••"}))
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "input", "placeholder": "At least 8 characters"}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "input", "placeholder": "Repeat new password"}))

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        pwd = (self.cleaned_data.get("current_password") or "").strip()
        if not self.user.check_password(pwd):
            raise forms.ValidationError("Current password is incorrect.")
        return pwd

    def clean(self):
        data = super().clean()
        p1 = (data.get("new_password") or "").strip()
        p2 = (data.get("confirm_password") or "").strip()
        if p1 and len(p1) < 8:
            self.add_error("new_password", "Password must be at least 8 characters.")
        if p1 and p2 and p1 != p2:
            self.add_error("confirm_password", "Passwords do not match.")
        # Use Django's validators for consistency
        if p1:
            try:
                password_validation.validate_password(p1, self.user)
            except forms.ValidationError as e:
                self.add_error("new_password", e)
        return data
