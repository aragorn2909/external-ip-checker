# Afraid IP Sync
# Copyright (C) 2026 [YOUR_USERNAME]
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

FROM alpine:latest

# Install system dependencies including tzdata and su-exec
RUN apk add --no-cache curl bind-tools python3 py3-flask tzdata su-exec

# Set working directory
WORKDIR /app

# Create data directory for persistent configuration
RUN mkdir -p /app/data

# Copy application files
COPY . /app

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh

# Expose the Web UI port
EXPOSE 7777

# Use entrypoint script to fix permissions and start app
ENTRYPOINT ["/app/entrypoint.sh"]
