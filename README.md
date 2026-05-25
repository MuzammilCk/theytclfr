# ytclfr

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)](https://fastapi.tiangolo.com)
[![Celery](https://img.shields.io/badge/Celery-5.0+-lightgreen.svg)](https://docs.celeryq.dev/en/stable/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**ytclfr** is a comprehensive YouTube video intelligence pipeline. It accepts a single YouTube video URL, automatically extracts all structured and meaningful content (including spoken words via speech-to-text, and on-screen text via OCR), identifies the video type (e.g., recipe, product list, script), and returns a structured JSON response complete with timestamps, confidence scores, and provenance data.

## 🚀 Key Features

- **Automated Video Ingestion:** Downloads and manages YouTube videos automatically via `yt-dlp`.
- **Speech-to-Text (ASR):** Precise transcriptions with word-level timestamps using `faster-whisper`.
- **Optical Character Recognition (OCR):** Frame-level on-screen text extraction via `Tesseract`.
- **Temporal Alignment:** Intelligently merges ASR and OCR data into a unified timeline.
- **LLM-Powered Structuring:** Utilizes local models (Ollama/llama3.1) for fast routine extraction and cloud models (Groq/llama-3.3-70b) for complex reasoning.
- **Content Classification:** Accurately classifies video content types (e.g., recipe, movie_list, summary).
- **Asynchronous Architecture:** Highly scalable and distributed execution via Celery and Redis.
- **Vector Search:** Built-in semantic search capabilities using PostgreSQL and the `pgvector` extension.

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

- [**System Architecture (`docs/ARCHITECTURE.md`)**](docs/ARCHITECTURE.md) - Learn about the high-level data flow, core components, and the transition from V1 to the evidence-based late binding pipeline of V2.
- [**Local Setup Guide (`docs/LOCAL_SETUP.md`)**](docs/LOCAL_SETUP.md) - Step-by-step instructions for setting up the development environment, databases, and dependencies on your local machine.
- [**Runbook (`docs/runbook.md`)**](docs/runbook.md) - Troubleshooting and incident response guidelines for operational issues.

## 🛠️ Quick Start

To quickly get the pipeline running locally:

1. Clone the repository and install dependencies:
   ```bash
   git clone https://github.com/your-org/ytclfr.git
   cd ytclfr
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
2. Set up your `.env` file based on `.env.example`.
3. Ensure PostgreSQL (with pgvector), Redis, and Ollama are running.
4. Run migrations:
   ```bash
   alembic upgrade head
   ```
5. Start the API server:
   ```bash
   uvicorn src.ytclfr.main:app --reload --host 0.0.0.0 --port 8000
   ```
6. Start the Celery Worker (in a separate terminal):
   ```bash
   celery -A src.ytclfr.worker worker --loglevel=info
   ```

*For detailed setup instructions, please refer to the [Local Setup Guide](docs/LOCAL_SETUP.md).*

## 🏗️ Tech Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic v2
- **Task Queue:** Celery 5, Redis 7
- **Database:** PostgreSQL 16 (with pgvector via Supabase)
- **AI & ML:** faster-whisper (CPU), Tesseract 5, Ollama (llama3.1:8b, nomic-embed-text), Groq (llama-3.3-70b-versatile)
- **Storage:** AWS S3 (boto3) for distributed media, local transient FS

## 🤝 Contributing

This project strictly adheres to the architectural guidelines outlined in the system context. No new libraries or dependencies may be added without explicit review and inclusion in the `decisions.md` log. Please ensure all tests pass (`pytest`) and linting rules are met (`ruff`, `mypy`) before submitting a pull request.