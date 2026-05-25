# Local Development Setup Guide

This document outlines the complete setup process for running the `ytclfr` video intelligence pipeline on your local machine.

## 1. Prerequisites

Ensure your system has the following dependencies installed before proceeding:
- **Python:** 3.11 or higher
- **PostgreSQL:** 16.0 or higher (with `pgvector` extension enabled)
- **Redis:** 7.0 or higher
- **Tesseract OCR:** 5.0 or higher
- **FFmpeg & yt-dlp:** Required for video downloading and frame sampling
- **Ollama:** Installed and running locally

## 2. System Dependencies Installation

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install redis-server postgresql postgresql-contrib ffmpeg tesseract-ocr
```

### macOS (Homebrew)
```bash
brew install redis postgresql@16 ffmpeg tesseract yt-dlp
brew services start redis
brew services start postgresql@16
```

### Windows
- Use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) (Recommended) or install the binaries directly.
- Tesseract OCR for Windows: [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
- Redis for Windows: Memurai or via WSL2.
- FFmpeg: Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add to system PATH.

## 3. Project Initialization

### 3.1 Clone the Repository
```bash
git clone https://github.com/your-org/ytclfr.git
cd ytclfr
```

### 3.2 Setup Python Virtual Environment
We recommend using standard `venv` or `hatch`:
```bash
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

### 3.3 Install Dependencies
Install the package in editable mode along with development dependencies:
```bash
pip install -e ".[dev]"
```

## 4. External Services Setup

### 4.1 PostgreSQL Database
1. Create a database for the project:
```sql
CREATE DATABASE ytclfr_dev;
```
2. Connect to the database and enable the `pgvector` extension:
```sql
\c ytclfr_dev
CREATE EXTENSION IF NOT EXISTS vector;
```

### 4.2 Ollama (Local LLM & Embeddings)
Ensure Ollama is running and download the required models:
```bash
ollama serve
ollama run llama3.1:8b
ollama pull nomic-embed-text
```

### 4.3 YouTube Cookies (Optional but Recommended)
For downloading age-restricted or rate-limited videos, export cookies from your browser (e.g., using a browser extension) in Netscape format and save them as `cookies.txt` in the project root.

## 5. Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```
2. Open `.env` and configure the following essential variables:
   - `DATABASE_URL`: Set to your local Postgres instance (e.g., `postgresql://postgres:password@localhost:5432/ytclfr_dev`)
   - `REDIS_URL`: Set to your local Redis (e.g., `redis://localhost:6379/0`)
   - `GROQ_API_KEY`: Provide your Groq API key for cloud reasoning tasks
   - `AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY`: Required if using S3 for temp storage
   - `YTDLP_COOKIES_FILE`: Absolute path to your `cookies.txt` (if applicable)

## 6. Database Migrations

Apply the Alembic migrations to set up the database schema:
```bash
alembic upgrade head
```

## 7. Running the Application

To run the full pipeline locally, you need to start the API server and the Celery worker pool in separate terminal instances.

### Terminal 1: FastAPI Server
```bash
uvicorn src.ytclfr.main:app --reload --host 0.0.0.0 --port 8000
```
The API documentation will be available at `http://localhost:8000/docs`.

### Terminal 2: Celery Worker
Ensure Redis is running, then start the worker:
```bash
celery -A src.ytclfr.worker worker --loglevel=info --concurrency=2
```

## 8. Running Tests
To verify the setup, run the test suite using pytest:
```bash
pytest tests/
```

## 9. Troubleshooting

- **yt-dlp bot detection errors:** Ensure your `cookies.txt` is up-to-date and correctly referenced in `.env`.
- **Tesseract not found:** If installed in a custom location (especially on Windows), update the `TESSERACT_CMD_PATH` in your `.env`.
- **OOM during processing:** Reduce `WORKER_CONCURRENCY` in `.env` if local LLMs/ASR models are consuming too much memory.
