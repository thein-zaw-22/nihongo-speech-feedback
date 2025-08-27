from django import forms

class AudioUploadForm(forms.Form):
    audio_file = forms.FileField(required=False)
    text_input = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter Japanese text here...'}))
    
    def clean(self):
        cleaned_data = super().clean()
        audio_file = cleaned_data.get('audio_file')
        text_input = cleaned_data.get('text_input')
        
        if not audio_file and not text_input:
            raise forms.ValidationError('Please provide either an audio file or text input.')
        
        return cleaned_data
