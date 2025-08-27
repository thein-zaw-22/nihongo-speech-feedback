from django import forms

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
