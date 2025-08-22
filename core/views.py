import os
import json
import whisper
from openai import OpenAI
import logging
from logging import Formatter
from django.shortcuts import render
from .forms import AudioUploadForm
from .models import Transcription
import tempfile

# Configure logger
logger = logging.getLogger(__name__)

# Load the local Whisper model
model = whisper.load_model("base")
# Initialize OpenAI client (gpt-4o-mini)
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def index(request):
    # Capture debug logs for this request
    logs = []
    class ListHandler(logging.Handler):
        def emit(self, record):
            logs.append(self.format(record))
    handler = ListHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    try:
        logger.debug("Index view called, method=%s", request.method)
        if request.method == 'POST':
            logger.debug("Received POST request with audio upload")
            form = AudioUploadForm(request.POST, request.FILES)
            if form.is_valid():
                audio = form.cleaned_data['audio_file']
                logger.debug("Form is valid. Audio file: %s", audio.name)

                tmp_path = None
                try:
                    # Save uploaded file to a temporary file that is not deleted on close
                    suffix = os.path.splitext(audio.name)[1] or '.wav'
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        for chunk in audio.chunks():
                            tmp_file.write(chunk)
                        tmp_path = tmp_file.name
                    logger.debug("Saved uploaded file to %s", tmp_path)

                    # Transcribe with Whisper
                    result = model.transcribe(tmp_path)
                    sentence = result.get('text', '')
                    logger.debug("Transcribed sentence: %s", sentence)

                    # Prepare GPT messages for structured JSON feedback
                    messages = [
                        {"role": "system", "content": (
                            "You are a professional Japanese language tutor. "
                            "Always correct unnatural or grammatical but awkward phrasing to the most natural Japanese usage. "
                            "When I send a Japanese sentence, respond with only a JSON object with two keys: `corrected_text` and `corrections`. "
                            "`corrected_text` must be the full corrected sentence. "
                            "`corrections` must be an array of objects with `original`, `corrected`, and `explanation` fields. "
                            "If the sentence is already the most natural usage, return it unchanged in `corrected_text` and an empty `corrections` array. "
                            "Do not include extra text, markdown, or formatting. explanation should be English and concise. "
                            "Example: {\"corrected_text\": \"水を飲みました。\", \"corrections\": "
                            "[{\"original\": \"水は飲みました。\", \"corrected\": \"水を飲みました。\", "
                            "\"explanation\": \"Use 'を' for the direct object instead of topic particle 'は'\"}]}"
                        )},
                        {"role": "user", "content": sentence}
                    ]
                    logger.debug("Sending messages to OpenAI: %s", messages)

                    # Call OpenAI GPT-4o-mini
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages
                    )
                    raw = response.choices[0].message.content
                    logger.debug("Raw feedback from OpenAI: %s", raw)

                    # Parse JSON feedback (with fallback to clean JSON substring)
                    try:
                        feedback_data = json.loads(raw)
                    except json.JSONDecodeError:
                        try:
                            start = raw.find('{')
                            end = raw.rfind('}') + 1
                            snippet = raw[start:end]
                            feedback_data = json.loads(snippet)
                        except json.JSONDecodeError:
                            feedback_data = {
                                "corrected_text": sentence,
                                "corrections": [],
                                "raw": raw
                            }
                            logger.debug("Failed to parse JSON, using raw feedback and assuming no corrections")

                    # Save result
                    record = Transcription.objects.create(
                        audio_file=audio,
                        transcript=sentence,
                        feedback=feedback_data
                    )
                    logger.debug("Transcription record created with id %s", record.id)

                    return render(request, 'result.html', {'result': record, 'logs': logs})
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        logger.debug("Cleaning up temporary file: %s", tmp_path)
                        os.remove(tmp_path)
        else:
            form = AudioUploadForm()

        return render(request, 'index.html', {'form': form})

    finally:
        logger.removeHandler(handler)