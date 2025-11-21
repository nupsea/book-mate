FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from official uv image (more reliable than install script)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files and lock file
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Create directories for mounted volumes
RUN mkdir -p DATA INDEXES

# Install Python dependencies using uv sync (uses exact versions from uv.lock)
RUN uv sync --frozen --no-dev

# Ensure model is present in the image
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

# Disable Python output buffering for real-time logs
ENV PYTHONUNBUFFERED=1

# Expose Gradio port
EXPOSE 7860

# Run the app using uv's managed environment
CMD ["uv", "run", "python", "-u", "-m", "src.ui.app"]
