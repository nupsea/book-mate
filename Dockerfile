FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Create directories for mounted volumes
RUN mkdir -p DATA INDEXES

# Install Python dependencies directly with pip
RUN pip install --no-cache-dir -e .

# Disable Python output buffering for real-time logs
ENV PYTHONUNBUFFERED=1

# Expose Gradio port
EXPOSE 7860

# Run the app
CMD ["python", "-u", "-m", "src.ui.app"]
