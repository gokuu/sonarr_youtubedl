FROM python:alpine

# Install ffmpeg and su-exec
RUN apk add --no-cache ffmpeg su-exec

# Copy and install requirements with optimizations
COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# create some files / folders
RUN mkdir -p /config /app /sonarr_root /logs && \
    touch /var/lock/sonarr_youtube.lock

# add volumes
VOLUME /config
VOLUME /sonarr_root
VOLUME /logs

# add local files
COPY app/ /app

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh

# update file permissions
RUN \
    chmod a+x \
    /app/sonarr_youtubedl.py \ 
    /app/utils.py \
    /app/config.yml.template \
    /entrypoint.sh

# ENV setup
ENV CONFIGPATH /config/config.yml

ENTRYPOINT ["/entrypoint.sh"]
CMD [ "python", "-u", "/app/sonarr_youtubedl.py" ]
