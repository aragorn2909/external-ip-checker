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

# Install system dependencies including tzdata for timezone support
RUN apk add --no-cache curl bind-tools python3 py3-flask tzdata

# Set working directory
WORKDIR /app

# Create data directory for persistent configuration
RUN mkdir -p /app/data

# Copy application files (including app.py and any dependencies)
COPY . /app

# Expose the Web UI port
EXPOSE 7777

# Start the application with diagnostics
CMD ["sh", "-c", "ls -R /app && python3 -u /app/app.py"]
