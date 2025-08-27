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
from django.utils import timezone
from datetime import datetime, time
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from .forms import AudioUploadForm
from .models import Transcription
from .models import GrammarQuestion, GrammarChoice, GrammarGameSession

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
def home(request):
    # Dashboard with cards to routes
    # Keep remembering provider selection for AI feedback card deep-link
    selected_provider = request.session.get('llm_provider')
    return render(request, 'home.html', {'selected_provider': selected_provider})


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
                # Persist selection in session for future visits
                try:
                    request.session['llm_provider'] = selected_provider
                except Exception:
                    pass
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

                # Record which provider produced this feedback
                if isinstance(feedback_data, dict):
                    feedback_data['provider'] = selected_provider

                record = Transcription.objects.create(
                    user=request.user,
                    audio_file=audio if audio else None,
                    transcript=sentence,
                    feedback=feedback_data,
                )
                logger.debug("Saved Transcription id=%s", record.id)

                # Redirect to feedback page, carrying provider for display
                return redirect(f"/feedback/{record.id}/?provider={selected_provider}")
        else:
            # Get provider from URL parameter if available
            selected_provider = request.GET.get('provider') or request.session.get('llm_provider', 'gemini')
            form = AudioUploadForm(initial={'llm_provider': selected_provider})

        return render(request, 'index.html', {'form': form})

    finally:
        logger.removeHandler(handler)


@login_required
def feedback(request, pk):
    try:
        obj = Transcription.objects.get(pk=pk)
    except Transcription.DoesNotExist:
        return redirect('index')
    selected_provider = request.GET.get('provider') or (obj.feedback.get('provider') if isinstance(obj.feedback, dict) else None)
    return render(request, 'result.html', {'result': obj, 'selected_provider': selected_provider})


@login_required
def history(request):
    items = Transcription.objects.filter(user=request.user).order_by('-created_at')
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    tz = timezone.get_current_timezone()
    start_dt = end_dt = None
    # Parse YYYY-MM-DD safely
    try:
        if start_str:
            d = datetime.strptime(start_str, '%Y-%m-%d').date()
            start_dt = timezone.make_aware(datetime.combine(d, time.min), tz)
    except Exception:
        start_str = None
    try:
        if end_str:
            d = datetime.strptime(end_str, '%Y-%m-%d').date()
            end_dt = timezone.make_aware(datetime.combine(d, time.max), tz)
    except Exception:
        end_str = None
    # Validate range first: end must not be earlier than start
    if start_dt and end_dt and end_dt < start_dt:
        messages.error(request, 'End date cannot be earlier than start date.')
        # Show no results to make the error obvious
        items = Transcription.objects.none()
    else:
        # Apply filters only if valid
        if start_dt:
            items = items.filter(created_at__gte=start_dt)
        if end_dt:
            items = items.filter(created_at__lte=end_dt)
    return render(request, 'history.html', {'items': items, 'start': start_str, 'end': end_str})


@login_required
def flashcard(request):
    # Placeholder page for Flashcard feature
    return render(request, 'flashcard.html')


@login_required
def pronunciation(request):
    # Placeholder page for Pronunciation Coach
    return render(request, 'pronunciation.html')


@login_required
def grammar_game(request):
    # Placeholder page for Grammar Game
    return render(request, 'grammar_game.html')


@login_required
def grammar_play(request):
    # Returns JSON set of questions for selected level/category
    level = request.GET.get('level', 'N5')
    category = request.GET.get('category', 'particle')
    try:
        n = max(1, min(int(request.GET.get('n', '10')), 30))
    except Exception:
        n = 10
    qs = GrammarQuestion.objects.filter(jlpt_level=level, category=category, is_active=True).prefetch_related('choices').order_by('?')[:n]
    items = []
    for q in qs:
        choices = list(q.choices.all().values('text', 'is_correct'))
        items.append({
            'id': q.id,
            'prompt': q.prompt,
            'explanation': q.explanation,
            'jlpt_level': q.jlpt_level,
            'category': q.category,
            'choices': choices,
        })
    from django.http import JsonResponse
    return JsonResponse({'items': items})


@login_required
def grammar_submit(request):
    # Save session results (AJAX)
    from django.http import JsonResponse
    try:
        payload = json.loads(request.body.decode('utf-8'))
        level = payload.get('level', 'N5')
        category = payload.get('category', 'particle')
        total = int(payload.get('total', 0))
        correct = int(payload.get('correct', 0))
        duration = int(payload.get('duration', 0))
        best_streak = int(payload.get('best_streak', 0))
        timer_enabled = bool(payload.get('timer_enabled', False))
        detail_data = {
            'best_streak': best_streak,
            'timer_enabled': timer_enabled,
        }
        GrammarGameSession.objects.create(
            user=request.user,
            jlpt_level=level,
            category=category,
            total_questions=total,
            correct=correct,
            duration_seconds=duration,
            details=detail_data
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
def grammar_explain(request):
    from django.http import JsonResponse
    try:
        payload = json.loads(request.body.decode('utf-8'))
        prompt = payload.get('prompt', '')
        level = payload.get('level', '')
        category = payload.get('category', '')
        user_answer = payload.get('user_answer', '')
        correct_text = payload.get('correct_text', '')
        # Build a dedicated prompt asking for rich JSON
        system = (
            "You are a concise Japanese grammar coach. "
            "Return ONLY a JSON object with keys: summary (1-2 sentences), why_correct, why_incorrect, "
            "grammar_point (name + 1 line), examples (array of 2 short natural examples), tips (array of 2-3 short tips). "
            "Use clear English; include Japanese in examples. Do not include any extra text outside JSON."
        )
        user = (
            f"JLPT level: {level}\nCategory: {category}\nQuestion: {prompt}\n"
            f"User answer: {user_answer}\nCorrect answer: {correct_text}"
        )
        provider = request.session.get('llm_provider') or LLM_PROVIDER
        try:
            if provider == 'openai':
                client = get_client('openai')
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role":"system","content":system},{"role":"user","content":user}]
                )
                raw = resp.choices[0].message.content
            elif provider == 'gemini':
                client = get_client('gemini')
                raw = client.generate_content(system + "\n\n" + user).text
            elif provider == 'bedrock':
                client = get_client('bedrock')
                resp = client.converse(
                    modelId=BEDROCK_MODEL_ID,
                    messages=[{"role":"user","content":[{"text":user}]}],
                    system=[{"text":system}],
                    inferenceConfig={"maxTokens":400, "temperature":0.3}
                )
                raw = resp['output']['message']['content'][0]['text']
            else:
                raw = json.dumps({"summary":"Unsupported provider","why_correct":"","why_incorrect":"","grammar_point":"","examples":[],"tips":[]})
            # Parse JSON (attempt to extract braces if provider adds text)
            try:
                obj = json.loads(raw)
            except Exception:
                start = raw.find('{'); end = raw.rfind('}')+1
                obj = json.loads(raw[start:end]) if start >=0 and end>start else {"summary": raw}
        except Exception as e:
            obj = {"summary": f"Explanation unavailable: {e}", "why_correct":"", "why_incorrect":"", "grammar_point":"", "examples":[], "tips":[]}
        return JsonResponse({'ok': True, 'explanation': obj})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
def grammar_history(request):
    # Filter per-user sessions
    qs = GrammarGameSession.objects.filter(user=request.user).order_by('-created_at')
    level = request.GET.get('level')
    category = request.GET.get('category')
    if level:
        qs = qs.filter(jlpt_level=level)
    if category:
        qs = qs.filter(category=category)
    best = qs.order_by('-details__best_streak', '-correct').first()
    return render(request, 'grammar_history.html', {
        'items': qs,
        'filter_level': level or '',
        'filter_category': category or '',
        'best': best,
    })


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
