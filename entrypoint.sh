#!/bin/bash

# Set default values if not provided
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Create group if it doesn't exist
if ! getent group sonarrytdlp > /dev/null 2>&1; then
    groupadd -g ${PGID} sonarrytdlp
fi

# Create user if it doesn't exist
if ! getent passwd sonarrytdlp > /dev/null 2>&1; then
    useradd -u ${PUID} -g ${PGID} -d /config -s /bin/bash sonarrytdlp
fi

# Update user/group IDs if they differ from current
current_uid=$(id -u sonarrytdlp 2>/dev/null || echo "0")
current_gid=$(id -g sonarrytdlp 2>/dev/null || echo "0")

if [ "$current_uid" != "$PUID" ] || [ "$current_gid" != "$PGID" ]; then
    # Update group ID
    groupmod -g ${PGID} sonarrytdlp
    # Update user ID
    usermod -u ${PUID} -g ${PGID} sonarrytdlp
fi

# Ensure proper ownership of directories
chown -R ${PUID}:${PGID} /config /logs /var/lock/sonarr_youtube.lock

# If running as root, switch to sonarrytdlp user
if [ "$(id -u)" = "0" ]; then
    exec gosu sonarrytdlp "$@"
else
    # Already running as non-root, execute directly
    exec "$@"
fi