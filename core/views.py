import os
import json
import whisper
import boto3
from openai import OpenAI
import logging
from logging import Formatter
from django.shortcuts import render
from .forms import AudioUploadForm
from .models import Transcription
import tempfile

# Configure logger
logger = logging.getLogger(__name__)

# --- LLM Provider Configuration ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
logger.info("Using LLM provider: %s", LLM_PROVIDER)

llm_client = None
if LLM_PROVIDER == "openai":
    llm_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
elif LLM_PROVIDER == "bedrock":
    aws_region = os.getenv("AWS_REGION_NAME", "us-east-1")
    llm_client = boto3.client(
        "bedrock-runtime",
        region_name=aws_region,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
else:
    raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")
# --------------------------------

# Load the local Whisper model
model = whisper.load_model("base")

def get_openai_feedback(transcript_text):
    """Gets feedback from OpenAI's GPT model."""
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
        {"role": "user", "content": transcript_text}
    ]
    logger.debug("Sending messages to OpenAI: %s", messages)
    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    return response.choices[0].message.content

def get_bedrock_feedback(transcript_text):
    """Gets feedback from Amazon Bedrock using the Converse API."""
    system_prompt = (
        "You are a professional Japanese language tutor. "
        "Your task is to correct Japanese sentences to be more natural. "
        "Respond with ONLY a valid JSON object containing `corrected_text` and `corrections` keys. "
        "`corrected_text` should be the full, corrected sentence. "
        "`corrections` should be an array of objects, each with `original`, `corrected`, and `explanation` fields. "
        "The explanation must be concise and in English. If no correction is needed, return the original text and an empty array. "
        "Do not add any text before or after the JSON object."
    )
    messages = [{"role": "user", "content": transcript_text}]

    logger.debug("Sending messages to Bedrock (amazon.nova-lite-v1:0): %s", messages)
    response = llm_client.converse(
        modelId="amazon.nova-lite-v1:0",
        messages=messages,
        system=[{"text": system_prompt}],
        inferenceConfig={"maxTokens": 2048, "temperature": 0.5}
    )

    raw_response = response['output']['message']['content'][0]['text']
    logger.debug("Raw feedback from Bedrock: %s", raw_response)
    return raw_response

def get_llm_feedback(transcript_text):
    """Dispatches to the configured LLM provider."""
    if LLM_PROVIDER == "openai":
        return get_openai_feedback(transcript_text)
    elif LLM_PROVIDER == "bedrock":
        return get_bedrock_feedback(transcript_text)
    # This should not be reached due to the initial check
    raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

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

                    # Get feedback from the configured LLM provider
                    raw = get_llm_feedback(sentence)

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