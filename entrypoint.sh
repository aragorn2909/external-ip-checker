#!/bin/sh
# entrypoint.sh - Automatically fix permissions for bind mounts

# Default to UID/GID 1000 if not provided
USER_ID=${PUID:-1000}
GROUP_ID=${PGID:-1000}

echo "Ensuring /app/data is owned by UID $USER_ID and GID $GROUP_ID..."

# Ensure the directory exists
mkdir -p /app/data

# Change ownership of the data directory and all its contents
chown -R "$USER_ID:$GROUP_ID" /app/data

# Execute the application as the requested user
echo "Starting application as UID $USER_ID..."
exec su-exec "$USER_ID:$GROUP_ID" python3 -u /app/app.py
