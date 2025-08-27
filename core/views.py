import os
import json
import boto3
import tempfile
from botocore.exceptions import ClientError
from openai import OpenAI
import google.generativeai as genai
import logging
from logging import Formatter
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from .forms import AudioUploadForm
from .models import Transcription

# Configure logger
logger = logging.getLogger(__name__)

# --- LLM Provider Configuration ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
logger.info("Using LLM provider: %s", LLM_PROVIDER)

# Model configurations
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash-lite")

# Configure Gemini once
if os.getenv('GEMINI_API_KEY'):
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def get_client(provider):
    """Get client for the specified provider."""
    if provider == "openai":
        return OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    elif provider == "gemini":
        return genai.GenerativeModel(GEMINI_MODEL_ID)
    elif provider == "bedrock":
        session = boto3.session.Session()
        aws_region = (
            os.getenv("AWS_REGION_NAME")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or session.region_name
            or "us-east-1"
        )
        _client_kwargs = {"region_name": aws_region}
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            _client_kwargs.update({
                "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
                "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
            })
            if os.getenv("AWS_SESSION_TOKEN"):
                _client_kwargs["aws_session_token"] = os.getenv("AWS_SESSION_TOKEN")
        return boto3.client("bedrock-runtime", **_client_kwargs)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
# --------------------------------

# Whisper transcription support
try:
    import whisper
except Exception:
    whisper = None

_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if whisper is None:
        raise RuntimeError("Whisper is not available in this environment")
    if _whisper_model is None:
        _whisper_model = whisper.load_model(os.getenv("WHISPER_MODEL", "base"))
    return _whisper_model

def transcribe_audio(uploaded_file):
    suffix = os.path.splitext(uploaded_file.name)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name
    try:
        model = get_whisper_model()
        result = model.transcribe(tmp_path, fp16=False, language='ja')
        return (result.get('text') or '').strip()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

def get_openai_feedback(transcript_text):
    """Gets feedback from OpenAI's GPT model."""
    client = get_client("openai")
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
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    return response.choices[0].message.content

def get_gemini_feedback(transcript_text):
    """Gets feedback from Google Gemini model."""
    client = get_client("gemini")
    prompt = (
        "You are a professional Japanese language tutor. "
        "Your task is to correct Japanese sentences to be more natural. "
        "Respond with ONLY a valid JSON object containing `corrected_text` and `corrections` keys. "
        "`corrected_text` should be the full, corrected sentence. "
        "`corrections` should be an array of objects, each with `original`, `corrected`, and `explanation` fields. "
        "The explanation must be concise and in English. If no correction is needed, return the original text and an empty array. "
        "Do not add any text before or after the JSON object.\n\n"
        f"Japanese text: {transcript_text}"
    )
    
    logger.debug("Sending prompt to Gemini (%s): %s", GEMINI_MODEL_ID, prompt[:100])
    try:
        response = client.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error("Gemini API error: %s", str(e))
        fallback = {
            "corrected_text": transcript_text,
            "corrections": [],
            "error": f"Gemini API error: {str(e)}"
        }
        return json.dumps(fallback)

def get_bedrock_feedback(transcript_text):
    """Gets feedback from Amazon Bedrock using the Converse API."""
    client = get_client("bedrock")
    system_prompt = (
        "You are a professional Japanese language tutor. "
        "Your task is to correct Japanese sentences to be more natural. "
        "Respond with ONLY a valid JSON object containing `corrected_text` and `corrections` keys. "
        "`corrected_text` should be the full, corrected sentence. "
        "`corrections` should be an array of objects, each with `original`, `corrected`, and `explanation` fields. "
        "The explanation must be concise and in English. If no correction is needed, return the original text and an empty array. "
        "Do not add any text before or after the JSON object."
    )
    messages = [{"role": "user", "content": [{"text": transcript_text}]}]

    logger.debug(
        "Sending messages to Bedrock (%s, region=%s): %s",
        BEDROCK_MODEL_ID,
        os.getenv("AWS_REGION_NAME", "us-east-1"),
        messages,
    )
    try:
        response = client.converse(
            modelId=BEDROCK_MODEL_ID,
            messages=messages,
            system=[{"text": system_prompt}],
            inferenceConfig={"maxTokens": 300, "topP": 0.1, "temperature": 0.3},
            additionalModelRequestFields={"inferenceConfig": {"topK": 20}}
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code == "AccessDeniedException":
            logger.error(
                "Access denied invoking Bedrock modelId=%s in region=%s. "
                "Ensure your account has model access enabled in Bedrock Console > Model access, "
                "and your IAM principal has bedrock:InvokeModel permissions.",
                BEDROCK_MODEL_ID,
                os.getenv("AWS_REGION_NAME", "us-east-1"),
            )
            # Return a structured feedback payload with error info instead of 500
            fallback = {
                "corrected_text": transcript_text,
                "corrections": [],
                "error": (
                    "Access denied to Bedrock model. Check Bedrock model access and IAM permissions."
                ),
            }
            return json.dumps(fallback)
        elif code == "ValidationException":
            message = e.response.get("Error", {}).get("Message", "")
            if "on-demand throughput" in message or "inference profile" in message:
                logger.error(
                    "Model %s requires an inference profile. Set BEDROCK_INFERENCE_PROFILE_ARN to a valid profile ARN or ID.",
                    BEDROCK_MODEL_ID,
                )
            elif "not authorized" in message:
                logger.error(
                    "Account not authorized for Bedrock API. Enable Bedrock access in AWS Console."
                )
            else:
                logger.error("Bedrock validation error: %s", message)
            fallback = {
                "corrected_text": transcript_text,
                "corrections": [],
                "error": (
                    "Bedrock access issue. Check account permissions and model access."
                ),
            }
            return json.dumps(fallback)
        # For other errors, re-raise for visibility
        raise

    raw_response = response['output']['message']['content'][0]['text']
    logger.debug("Raw feedback from Bedrock: %s", raw_response)
    return raw_response

def get_llm_feedback(transcript_text, provider=None):
    """Dispatches to the specified LLM provider."""
    provider = provider or LLM_PROVIDER
    if provider == "openai":
        return get_openai_feedback(transcript_text)
    elif provider == "gemini":
        return get_gemini_feedback(transcript_text)
    elif provider == "bedrock":
        return get_bedrock_feedback(transcript_text)
    # This should not be reached due to the initial check
    raise ValueError(f"Unsupported LLM provider: {provider}")

@login_required
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
            logger.debug("Received POST request for analysis")
            form = AudioUploadForm(request.POST, request.FILES)
            if form.is_valid():
                audio = form.cleaned_data.get('audio_file')
                text_input = (form.cleaned_data.get('text_input') or '').strip()
                if not text_input and audio:
                    try:
                        text_input = transcribe_audio(audio)
                        logger.debug("Transcribed audio to: %s", text_input[:100].replace('\n',' '))
                    except Exception as e:
                        logger.error("Transcription failed: %s", str(e))
                        return render(request, 'index.html', {'form': form, 'error': f'Transcription failed: {str(e)}'})

                if not text_input:
                    return render(request, 'index.html', {'form': form, 'error': 'Please enter text or upload audio for analysis.'})

                sentence = text_input
                selected_provider = form.cleaned_data.get('llm_provider', 'gemini')
                raw = get_llm_feedback(sentence, selected_provider)

                # Parse JSON feedback (with fallback slice)
                try:
                    feedback_data = json.loads(raw)
                except json.JSONDecodeError:
                    try:
                        start = raw.find('{')
                        end = raw.rfind('}') + 1
                        snippet = raw[start:end]
                        feedback_data = json.loads(snippet)
                    except Exception as e:
                        logger.warning("Fallback JSON parse failed: %s", str(e))
                        feedback_data = {"corrected_text": sentence, "corrections": [], "raw": raw}

                record = Transcription.objects.create(
                    audio_file=audio if audio else None,
                    transcript=sentence,
                    feedback=feedback_data,
                )
                logger.debug("Saved Transcription id=%s", record.id)

                return render(request, 'result.html', {'result': record, 'logs': logs, 'selected_provider': selected_provider})
        else:
            # Get provider from URL parameter if available
            selected_provider = request.GET.get('provider', 'gemini')
            form = AudioUploadForm(initial={'llm_provider': selected_provider})

        return render(request, 'index.html', {'form': form})

    finally:
        logger.removeHandler(handler)


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})
