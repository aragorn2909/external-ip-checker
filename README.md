# Afraid IP Sync

A Dockerized dynamic DNS (DDNS) client and monitor for [Afraid.org (FreeDNS)](https://freedns.afraid.org/). This tool monitors your external IP address and automatically updates your DNS records if they mismatch. It features a clean Web UI for monitoring status and managing domains.

## Features

- **Live Dashboard**: Real-time status updates via AJAX polling—no refresh required.
- **Light/Dark Mode**: High-contrast, Material Design-compliant themes for any environment.
- **Account Import**: Easily sync all your domains directly from your Afraid.org account.
- **Auto-Sync**: Checks IP and DNS records periodically (configurable interval).
- **Manual Sync**: Force a sync or "Correct All" directly from the dashboard.
- **Timezone Support**: Display check-in times in your local timezone.
- **Lightweight**: Built on Alpine Linux with Python/Flask.

## Quick Start

The easiest way to run Afraid IP Sync is using Docker Compose.

1.  **Clone or copy the project files:**
    ```bash
    git clone https://github.com/aragorn2909/external-ip-checker.git
    cd external-ip-checker
    ```
    Ensure `app.py`, `Dockerfile`, and `compose.yaml` are all in the same directory.

    ```yaml
    services:
      afraid-ip-sync:
        image: afraid-ip-sync:latest
        build: .
        container_name: afraid-ip-sync
        ports:
          - "7777:7777"
        volumes:
          - ./data:/app/data
        environment:
          - TZ=UTC
        restart: unless-stopped
    ```

2.  **Launch the container:**

    ```bash
    docker compose up -d
    ```

3.  **Access the Dashboard:**
    Open your browser and navigate to `http://localhost:7777`.

## Configuration

### Initial Setup

Once the container is running and you've accessed the UI:

1.  Go to **Settings**.
2.  (Optional but recommended) Enter your **Afraid.org Username and Password** and click **Save Credentials**.
3.  Click **Sync Domains from Account** to automatically import all your domains and their update tokens.
4.  Alternatively, use the **Add Domain Manually** form if you only want to monitor specific domains.

### Environment Variables

If you prefer to configure defaults via environment variables:

- `CHECK_INTERVAL`: Frequency of automatic checks in seconds (default: `1800`).
- `TZ`: Timezone for the dashboard display (e.g., `America/New_York`).

## Persistent Data

All domain configurations and settings are stored in `/app/data/config.json`. Mounting a volume to `./data` as shown in the example ensures your settings persist across container restarts and updates.

## Development

To run the application locally without Docker:

1.  Install dependencies:
    ```bash
    apk add curl bind-tools python3 py3-flask tzdata # Alpine
    # OR on other distros
    pip install flask
    ```
2.  Run the app:
    ```bash
    python3 app.py
    ```

## Troubleshooting

### "can't open file '/app/app.py': [Errno 2] No such file or directory"

If you see this error when running the container:

1.  **Check Files**: Ensure the `app.py` file is in the same directory as the `Dockerfile` when you run the build.
2.  **Force Rebuild**: Run `docker compose build --no-cache` and then `docker compose up -d` to ensure the image is built correctly with the local source files.
3.  **Permissions**: Ensure the user running Docker has read permissions for the project directory.

## License

This project is licensed under the **GNU General Public License v2.0 (GPL-2.0)**. See the [LICENSE](file:///home/aaron/.gemini/antigravity/scratch/external-ip-checker/LICENSE) file for the full license text.

---

Requests are welcome

*Note: This project is not affiliated with Afraid.org.*
