FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy application files first (needed for setuptools-scm to write _version.py)
COPY vim2vid/ ./vim2vid/
COPY pyproject.toml default.json default_greeting.json ./

# Use VERSION build arg to set version for setuptools-scm
ARG VERSION
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_VIM2VID=${VERSION}
RUN pip install --no-cache-dir -e .

# Create output directory
RUN mkdir -p /output

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command
ENTRYPOINT ["vim2vid"]
CMD ["--help"]