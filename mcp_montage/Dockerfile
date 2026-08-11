# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.11-slim

# Install system dependencies
# ffmpeg is required for video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fontconfig \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first to leverage cache
COPY pyproject.toml uv.lock ./

# Install Python dependencies (cached)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Pre-download the MMS_FA weights at build time and fast failure if offline.
# So runtime doesn’t need to fetch ~1.2 GB with TORCH_HOME cache reuse.
ENV TORCH_HOME=/app/.torch
RUN uv run --no-project python -c "from torchaudio.pipelines import MMS_FA as b; b.get_model(); b.get_tokenizer(); b.get_aligner()"

# Copy application code
COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Register bundled subtitle fonts with system fontconfig. The ffmpeg
# subtitles filter's fonts_dir only resolves the Fontname the ASS declares;
# libass's missing-glyph fallback for OTHER scripts routes through
# fontconfig, which must know about these fonts at the system level.
RUN mkdir -p /usr/local/share/fonts/montage \
    && find assets/fonts -type f \( -name "*.ttf" -o -name "*.otf" \) -exec cp {} /usr/local/share/fonts/montage/ \; \
    && fc-cache -f

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
