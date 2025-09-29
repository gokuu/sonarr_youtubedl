FROM python:3-alpine as builder

# Install build dependencies
RUN apk add --no-cache gcc musl-dev

# Copy requirements and install dependencies including PyInstaller
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pyinstaller

# Copy source code
COPY app/ /app

# Compile the application
WORKDIR /app
RUN pyinstaller --onefile --name sonarr_youtubedl sonarr_youtubedl.py

# Runtime stage - minimal image with just the executable
FROM alpine:latest

# Install runtime dependencies
RUN apk add --no-cache ffmpeg

# Create necessary directories and files
RUN mkdir -p /config /sonarr_root /logs && \
    touch /var/lock/sonarr_youtube.lock

# Copy the compiled executable from build stage
COPY --from=builder /app/dist/sonarr_youtubedl /usr/local/bin/sonarr_youtubedl
COPY --from=builder /app/config.yml.template /app/config.yml.template

# Set permissions
RUN chmod +x /usr/local/bin/sonarr_youtubedl /app/config.yml.template

# Add volumes
VOLUME /config
VOLUME /sonarr_root
VOLUME /logs

# ENV setup
ENV CONFIGPATH=/config/config.yml

CMD ["/usr/local/bin/sonarr_youtubedl"]
