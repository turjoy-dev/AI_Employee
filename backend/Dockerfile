FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system audio libraries required by Pipecat, Whisper, and Piper TTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python runtime dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend package and knowledge base documents
COPY backend ./backend
COPY knowledge_base ./knowledge_base

# Pre-warm Silero VAD, Faster-Whisper base, and Piper TTS voice models so first WebSocket call starts instantly
RUN python -c "from pipecat.audio.vad.silero import SileroVADAnalyzer; SileroVADAnalyzer()" && \
    python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')" && \
    python -c "from pipecat.services.piper.tts import PiperTTSService; PiperTTSService(use_cuda=False, settings=PiperTTSService.Settings(voice='en_US-lessac-medium'))"

# Ensure persistent volume mount directories exist
RUN mkdir -p /app/data /app/chroma_db

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
