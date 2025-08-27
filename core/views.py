import os
import json
import whisper
import boto3
from botocore.exceptions import ClientError
from openai import OpenAI
import google.generativeai as genai
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
# Optional Bedrock model configuration (used when LLM_PROVIDER=bedrock)
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
# Optional Gemini model configuration (used when LLM_PROVIDER=gemini)
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash-exp")
if LLM_PROVIDER == "openai":
    llm_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
elif LLM_PROVIDER == "gemini":
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    llm_client = genai.GenerativeModel(GEMINI_MODEL_ID)
    logger.info("Initialized Gemini client: modelId=%s", GEMINI_MODEL_ID)
elif LLM_PROVIDER == "bedrock":
    # Resolve region in priority order: custom var -> standard AWS vars -> boto session -> fallback
    session = boto3.session.Session()
    aws_region = (
        os.getenv("AWS_REGION_NAME")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or session.region_name
        or "us-east-1"
    )
    # Build client kwargs allowing default provider chain, but honoring env vars if set
    _client_kwargs = {"region_name": aws_region}
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        _client_kwargs.update({
            "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
            "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        })
        if os.getenv("AWS_SESSION_TOKEN"):
            _client_kwargs["aws_session_token"] = os.getenv("AWS_SESSION_TOKEN")
    llm_client = boto3.client("bedrock-runtime", **_client_kwargs)
    logger.info(
        "Initialized Bedrock client: region=%s, modelId=%s",
        aws_region,
        BEDROCK_MODEL_ID,
    )
else:
    raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}. Supported: openai, gemini, bedrock")
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

def get_gemini_feedback(transcript_text):
    """Gets feedback from Google Gemini model."""
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
        response = llm_client.generate_content(prompt)
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
        response = llm_client.converse(
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

def get_llm_feedback(transcript_text):
    """Dispatches to the configured LLM provider."""
    if LLM_PROVIDER == "openai":
        return get_openai_feedback(transcript_text)
    elif LLM_PROVIDER == "gemini":
        return get_gemini_feedback(transcript_text)
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
                audio = form.cleaned_data.get('audio_file')
                text_input = form.cleaned_data.get('text_input')
                
                if text_input:
                    # Direct text input - no transcription needed
                    sentence = text_input.strip()
                    logger.debug("Using direct text input: %s", sentence.replace('\n', '').replace('\r', '')[:100])
                else:
                    # Audio input - transcribe with Whisper
                    logger.debug("Form is valid. Audio file: %s", audio.name.replace('\n', '').replace('\r', ''))
                    tmp_path = None
                    try:
                        # Save uploaded file to a temporary file that is not deleted on close
                        suffix = os.path.splitext(audio.name)[1] or '.wav'
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                            for chunk in audio.chunks():
                                tmp_file.write(chunk)
                            tmp_path = tmp_file.name
                        logger.debug("Saved uploaded file to %s", tmp_path.replace('\n', '').replace('\r', ''))

                        # Transcribe with Whisper (explicitly set to Japanese)
                        result = model.transcribe(tmp_path, language='ja')
                        sentence = result.get('text', '')
                        logger.debug("Transcribed sentence: %s", sentence.replace('\n', '').replace('\r', '')[:100])
                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            logger.debug("Cleaning up temporary file: %s", tmp_path.replace('\n', '').replace('\r', ''))
                            os.remove(tmp_path)

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
                logger.debug("Transcription record created with id %s", str(record.id))

                return render(request, 'result.html', {'result': record, 'logs': logs})
        else:
            form = AudioUploadForm()

        return render(request, 'index.html', {'form': form})

    finally:
        logger.removeHandler(handler)
