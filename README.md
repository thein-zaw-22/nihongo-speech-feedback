## Whisper Feedback POC (Django)

AI-powered Japanese speaking feedback: upload or record audio, transcribe locally with Whisper, then get natural Japanese corrections and concise explanations from a configurable LLM provider.

### Overview
- Local transcription using `openai-whisper` (Whisper) with the `base` model
- Feedback generation using OpenAI `gpt-4o-mini` or Amazon Bedrock (configurable `BEDROCK_MODEL_ID`, default `amazon.nova-lite-v1:0`). Note: Amazon Nova models require an inference profile rather than on-demand.
- Django app with Postgres storage for uploaded audio, transcript, and structured feedback
- Simple UI for recording/uploading audio and viewing corrections

### Architecture
- `core/views.py`: handles uploads, runs Whisper transcription, calls the configured LLM provider, saves `Transcription`
- `core/models.py`: `Transcription` model (`audio_file`, `transcript`, `feedback` JSON, timestamps)
- `core/templates/`: `index.html` (record/upload) and `result.html` (transcript, corrections, debug logs)
- `whisper_feedback_poc/settings.py`: Postgres config (for Docker), media/static, dotenv load
- `Dockerfile` + `docker-compose.yml`: app container (with ffmpeg) and Postgres service

### Requirements
- LLM API Keys (see Configuration section)
- ffmpeg (already installed in the Docker image)
- If running locally without Docker: Python 3.10+, ffmpeg installed on host

### Quick start (Docker)
1) Create `.env` in the project root with your desired provider. For OpenAI:
```bash
echo "OPENAI_API_KEY=sk-..." > .env
```
For Amazon Bedrock (Nova via inference profile):
```bash
echo "LLM_PROVIDER=bedrock" > .env
echo "AWS_REGION_NAME=us-east-1" >> .env
echo "AWS_ACCESS_KEY_ID=..." >> .env
echo "AWS_SECRET_ACCESS_KEY=..." >> .env
# Optional if using temporary credentials
echo "AWS_SESSION_TOKEN=..." >> .env
# Nova requires an inference profile (use the exact ARN/ID from the Bedrock console)
echo "BEDROCK_MODEL_ID=amazon.nova-lite-v1:0" >> .env
echo "BEDROCK_INFERENCE_PROFILE_ARN=arn:aws:bedrock:<region>:aws:inference-profile/amazon.nova-lite-v1:0" >> .env

RPM limits (Requests Per Minute):
```bash
# Per-model caps used by the in-app limiter
echo "OPENAI_GPT4O_RPM=1000" >> .env
echo "OPENAI_GPT4O_MINI_RPM=3500" >> .env
echo "GEMINI_25_FLASH_LITE_RPM=15" >> .env
echo "AWS_NOVA_LITE_RPM=1000" >> .env
```
```

2) Build containers and run migrations once:
```bash
docker-compose build
docker-compose run --rm web python manage.py migrate
```

3) Start the stack:
```bash
docker-compose up
```

4) Open `http://localhost:8000` and:
- Click "Record" to capture audio in-browser, or click "Upload File" to select an audio file
- Click "Submit for Analysis" to transcribe and get feedback

Notes:
- The first transcription will download the Whisper `base` model, which can take time.
- Uploaded/recorded audio is stored under `media/uploads/`. Results are persisted in Postgres.

Optional (admin):
```bash
docker-compose exec web python manage.py createsuperuser
```
Admin URL: `http://localhost:8000/admin/`

### Local development without Docker (advanced)
Docker is recommended. If you prefer local:
- Install system ffmpeg (macOS): `brew install ffmpeg`
- Create and activate a virtualenv, then:
```bash
pip install --upgrade pip
pip install -r requirements.txt
# Create your .env file as described in the "Quick start" section
```

Database options:
- Easiest: run Postgres via Docker only, but point Django to `localhost` by editing `whisper_feedback_poc/settings.py` `DATABASES` to use `HOST: 'localhost'` (current settings assume `HOST: 'db'` inside Docker)
- Or switch to SQLite for quick testing (also requires editing `DATABASES` in settings)

Run migrations and server:
```bash
python manage.py migrate
python manage.py runserver
```

### Configuration
- Environment variables (loaded via `python-dotenv` from `.env`):
  - `LLM_PROVIDER`: The language model provider. Can be `openai` (default) or `bedrock`.
  - `OPENAI_API_KEY`: Required if `LLM_PROVIDER` is `openai`.
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`: Required if `LLM_PROVIDER` is `bedrock`.
  - `AWS_SESSION_TOKEN`: Optional, if using temporary credentials.
  - `BEDROCK_MODEL_ID`: Bedrock model ID for the Converse API. Defaults to `amazon.nova-lite-v1:0`. You must enable access to the chosen model in the Bedrock Console for your AWS account and region.
  - `BEDROCK_INFERENCE_PROFILE_ARN`: Required for Nova models. Set an inference profile ARN or ID and the app will call Converse with that profile. The app does not fall back to on-demand `modelId` for Bedrock.
  - Per-model RPM caps for the simple limiter (Requests Per Minute):
    - `OPENAI_GPT4O_RPM` (default 1000)
    - `OPENAI_GPT4O_MINI_RPM` (default 3500)
    - `GEMINI_25_FLASH_LITE_RPM` (default 15)
    - `AWS_NOVA_LITE_RPM` (default 1000)

- Django settings highlights:
  - `SECRET_KEY` is a placeholder in code; change it for any non-local use
  - `DEBUG=True` is set; do not use in production
  - `ALLOWED_HOSTS=[]`; adjust for deployments
  - Media: `MEDIA_URL=/media/`, `MEDIA_ROOT=media/`

### How it works
1) Whisper transcription
   - `core/views.py` loads the Whisper `base` model and transcribes the uploaded/recorded file
2) LLM Feedback
   - The transcript is sent to the configured LLM provider (OpenAI or Bedrock) with a strict system prompt to return JSON:
     `{ "corrected_text": string, "corrections": Array<{ original, corrected, explanation }> }`
   - The app parses the JSON, with a fallback that extracts a JSON block if the response contains extra text
3) Persistence
   - A `Transcription` row is saved with the uploaded audio, transcript, and feedback JSON
4) Presentation
   - `result.html` displays audio playback, transcript, corrected text, explanations, and optional debug logs

### Changing model choices
- Whisper size: edit `core/views.py` and change `whisper.load_model("base")` to e.g. `"small"`, `"medium"`, etc. Larger models are slower but more accurate.
- OpenAI model: edit the `model="gpt-4o-mini"` parameter in the `get_openai_feedback` function in `core/views.py`.
- Bedrock (Nova): set `BEDROCK_MODEL_ID=amazon.nova-lite-v1:0` and `BEDROCK_INFERENCE_PROFILE_ARN=<your profile ARN or ID>`. The app requires a profile for Bedrock usage by default.

### Bedrock model access
- In the AWS Console, open Amazon Bedrock and go to "Model access" to enable the models you want to use (e.g., Amazon Nova Lite, Anthropic Claude 3 Haiku). Without access, requests return `AccessDeniedException`.
- Ensure your IAM principal has `bedrock:InvokeModel` (and streaming variants if needed) permissions for the selected model(s) and region.
- Amazon Nova Lite/Pro/Micro cannot be invoked with on-demand throughput. If you see a `ValidationException` like "Invocation of model ID ... with on-demand throughput isn’t supported", set `BEDROCK_INFERENCE_PROFILE_ARN` to a valid inference profile that contains the target model.

### Supported audio formats
- Browser recording saves WebM/Opus. Upload accepts common audio formats; ffmpeg handles conversion and Whisper supports standard codecs.

### Troubleshooting
- ffmpeg not found (non-Docker): install via your OS package manager (e.g., `brew install ffmpeg`).
- OpenAI / Bedrock errors: ensure your `.env` has a valid API key/credentials for the selected provider, and your account has access/billing enabled.
- Postgres connection errors (non-Docker): the default `HOST='db'` only resolves inside Docker Compose. Use Docker for Postgres, or update settings for local `localhost`.
- Whisper model download slow: first run downloads weights; subsequent runs are faster.

### Not production-ready
- Do not expose with `DEBUG=True` and placeholder `SECRET_KEY`.
- Add proper `ALLOWED_HOSTS`, HTTPS, secrets management, and a production-ready database and static/media serving if deploying.
