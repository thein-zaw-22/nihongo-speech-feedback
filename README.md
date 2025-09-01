## AI Japanese Learning Platform (Django)

Comprehensive Japanese learning platform with AI-powered feedback, spaced repetition flashcards, interactive games, and mobile-friendly design.

### Features
- **AI Speaking Feedback**: Upload or record audio, transcribe with Whisper, get natural corrections from configurable LLM providers
- **Spaced Repetition Flashcards**: SM-2 algorithm for optimized vocabulary learning with progress tracking
- **Grammar Game**: Interactive multiple-choice questions with JLPT levels and categories
- **Syntax Puzzle**: Drag-and-drop sentence reconstruction with mobile touch support
- **Batch Processing**: CSV/Excel file correction for bulk text processing
- **Multi-Provider LLM**: OpenAI GPT, Google Gemini, or Amazon Bedrock support
- **Mobile-First Design**: Responsive UI optimized for both mobile and desktop

### Core Components
- Local transcription using `openai-whisper` (Whisper) with configurable models
- LLM feedback from OpenAI `gpt-4o-mini`, Google Gemini, or Amazon Bedrock
- Django app with Postgres storage and comprehensive admin interface
- Modern responsive UI with dark/light theme support

### Architecture
- **Backend**: Django with PostgreSQL, user authentication, and admin interface
- **Models**: Transcriptions, Flashcards with spaced repetition progress, Grammar questions, Puzzles, Batch jobs
- **Views**: Multi-provider LLM integration, spaced repetition algorithms, game logic, batch processing
- **Templates**: Mobile-responsive UI with modern card-based design and touch support
- **Docker**: Containerized deployment with ffmpeg support and database persistence

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

4) Open `http://localhost:8000` and explore:
- **Speak AI**: Record or upload audio for AI feedback
- **Flashcards**: Practice vocabulary with spaced repetition
- **Grammar Game**: Play interactive grammar quizzes
- **Puzzle**: Reconstruct Japanese sentences
- **Batch Correction**: Process CSV/Excel files in bulk

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
  - `LLM_PROVIDER`: Provider choice - `openai`, `gemini`, or `bedrock`
  - `OPENAI_API_KEY`: Required for OpenAI
  - `OPENAI_MODEL_ID`: OpenAI model (default: `gpt-4o-mini`)
  - `GEMINI_API_KEY`: Required for Google Gemini
  - `GEMINI_MODEL_ID`: Gemini model (default: `gemini-2.5-flash-lite`)
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`: Required for Bedrock
  - `AWS_SESSION_TOKEN`: Optional for temporary credentials
  - `BEDROCK_MODEL_ID`: Bedrock model (default: `us.amazon.nova-lite-v1:0`)
  - `BEDROCK_INFERENCE_PROFILE_ARN`: Required for Nova models
  - Per-model RPM limits for rate limiting:
    - `OPENAI_GPT4O_RPM`, `OPENAI_GPT4O_MINI_RPM`
    - `GEMINI_25_FLASH_LITE_RPM`
    - `AWS_NOVA_LITE_RPM`

- Django settings highlights:
  - `SECRET_KEY` is a placeholder in code; change it for any non-local use
  - `DEBUG=True` is set; do not use in production
  - `ALLOWED_HOSTS=[]`; adjust for deployments
  - Media: `MEDIA_URL=/media/`, `MEDIA_ROOT=media/`

### Technical Implementation

#### AI Feedback Pipeline
1. **Audio Processing**: Whisper transcribes uploaded/recorded audio to Japanese text
2. **LLM Analysis**: Configured provider analyzes text for naturalness and corrections
3. **Structured Response**: JSON format with corrected text and detailed explanations
4. **Persistence**: Results stored with user association and session tracking

#### Spaced Repetition Algorithm
1. **Initial Learning**: New cards start with 1-day intervals
2. **Performance Tracking**: User ratings (Again/Hard/Good/Easy) adjust scheduling
3. **Ease Factor Calculation**: SM-2 algorithm optimizes review intervals
4. **Smart Scheduling**: Cards reappear just before forgetting occurs

#### Mobile Touch Support
- **Touch Events**: Custom touch handlers for drag-and-drop on mobile
- **Visual Feedback**: Real-time positioning and drop zone highlighting
- **Gesture Recognition**: Distinguishes between taps, drags, and swipes
- **Cross-Platform**: Works consistently across iOS, Android, and desktop browsers

### Features in Detail

#### Spaced Repetition Flashcards
- **SM-2 Algorithm**: Scientifically proven spaced repetition scheduling
- **Progress Tracking**: Individual card progress with ease factors and intervals
- **Smart Scheduling**: Cards appear when you're about to forget them
- **Statistics Dashboard**: Real-time view of due, learned, and new cards
- **Admin Import**: Bulk import flashcards via CSV/JSON files

#### Grammar Game
- **JLPT Levels**: N5 to N1 difficulty progression
- **Categories**: Particles, verb forms, politeness, word order, vocabulary
- **Performance Tracking**: Session history with best streaks and accuracy
- **LLM Explanations**: AI-powered detailed explanations for wrong answers

#### Syntax Puzzle
- **Mobile Touch Support**: Drag and drop works on mobile browsers
- **Visual Feedback**: Particle linking with colored lines
- **Progressive Difficulty**: From basic to complex sentence structures
- **Instant Validation**: Real-time feedback with corrections

#### Batch Processing
- **File Support**: CSV and Excel file processing
- **Background Jobs**: Asynchronous processing with progress tracking
- **Bulk Corrections**: Process hundreds of sentences efficiently
- **Download Results**: Get corrected files with explanations

### Model Configuration
- **Whisper**: Set `WHISPER_MODEL` env var (`base`, `small`, `medium`, `large`)
- **OpenAI**: Configure via `OPENAI_MODEL_ID` (e.g., `gpt-4o-mini`, `gpt-4o`)
- **Gemini**: Set `GEMINI_MODEL_ID` for different Gemini variants
- **Bedrock**: Use `BEDROCK_MODEL_ID` with required inference profiles for Nova models

### Bedrock model access
- In the AWS Console, open Amazon Bedrock and go to "Model access" to enable the models you want to use (e.g., Amazon Nova Lite, Anthropic Claude 3 Haiku). Without access, requests return `AccessDeniedException`.
- Ensure your IAM principal has `bedrock:InvokeModel` (and streaming variants if needed) permissions for the selected model(s) and region.
- Amazon Nova Lite/Pro/Micro cannot be invoked with on-demand throughput. If you see a `ValidationException` like "Invocation of model ID ... with on-demand throughput isn’t supported", set `BEDROCK_INFERENCE_PROFILE_ARN` to a valid inference profile that contains the target model.

### Supported audio formats
- Browser recording saves WebM/Opus. Upload accepts common audio formats; ffmpeg handles conversion and Whisper supports standard codecs.

### Troubleshooting
- **ffmpeg not found**: Install via package manager (`brew install ffmpeg` on macOS)
- **LLM API errors**: Verify API keys and account access/billing for chosen provider
- **Database connection**: Use Docker for Postgres or update `HOST='localhost'` for local setup
- **Whisper downloads**: First run downloads model weights; subsequent runs are faster
- **Mobile touch issues**: Ensure `touch-action: none` CSS is applied to draggable elements
- **Migration errors**: Run `docker-compose exec web python manage.py migrate` after model changes

### Admin Features
- **Content Management**: Import/export flashcards, grammar questions, and puzzles
- **User Analytics**: View learning progress and session statistics
- **Batch Job Monitoring**: Track background processing jobs
- **File Format Support**: CSV and JSON import with validation

### Mobile Optimization
- **Touch-Friendly**: All interactions work on mobile devices
- **Responsive Design**: Adapts to all screen sizes
- **Swipe Gestures**: Natural mobile interactions
- **Offline-Ready**: Core features work without constant connectivity

### Production Deployment
- Change `SECRET_KEY` and set `DEBUG=False`
- Configure `ALLOWED_HOSTS` for your domain
- Set up HTTPS and proper static file serving
- Use production database with backups
- Implement proper secrets management
- Configure rate limiting and monitoring
