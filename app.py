#!/usr/bin/env python3
#
# Afraid IP Sync - A tool to monitor and update dynamic DNS for Afraid.org
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
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import time
import json
import subprocess
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
from threading import Thread
from typing import Dict, List, Any, Union

app = Flask(__name__)

@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    # Handle non-HTTP exceptions only
    return f'INTERNAL SERVER ERROR: {str(e)}', 500

app.secret_key = os.urandom(24)

CONFIG_PATH = os.path.join("/app/data", "config.json")

# Default config
default_config: Dict[str, Any] = {
    "domains": [],
    "global_interval": 1800,
    "afraid_user": "",
    "afraid_pass": "",
    "dashboard_user": "admin",
    "dashboard_pass": "admin",
    "timezone": "UTC",
    "theme": "light"
}

config: Dict[str, Any] = default_config.copy()

# State for status UI
state: Dict[str, Dict[str, Any]] = {
    "results": {}
}

def load_config() -> None:
    global config
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                saved_config = json.load(f)
                if isinstance(saved_config, dict):
                    config.update(saved_config)
                
                # Ensure structure and types are correct
                if not isinstance(config.get("domains"), list): 
                    config["domains"] = []
                
                # Sanitize domains list
                sanitized_domains: List[Dict[str, str]] = []
                for d in config["domains"]:
                    if isinstance(d, dict) and "domain" in d and "update_url" in d:
                        sanitized_domains.append({"domain": str(d["domain"]), "update_url": str(d["update_url"])})
                config["domains"] = sanitized_domains
                
                if not isinstance(config.get("global_interval"), (int, float)): 
                    config["global_interval"] = 1800
                else:
                    config["global_interval"] = int(config["global_interval"])
                    
                if not isinstance(config.get("afraid_user"), str): config["afraid_user"] = ""
                if not isinstance(config.get("afraid_pass"), str): config["afraid_pass"] = ""
                if not isinstance(config.get("dashboard_user"), str): config["dashboard_user"] = "admin"
                if not isinstance(config.get("dashboard_pass"), str): config["dashboard_pass"] = "admin"
                if not isinstance(config.get("timezone"), str): config["timezone"] = "UTC"
                if not isinstance(config.get("theme"), str): config["theme"] = "light"
        except Exception as e:
            print(f"Error loading config: {e}")

    # Override defaults with environment variables if provided and config is empty
    env_user = os.environ.get("DASHBOARD_USER")
    env_pass = os.environ.get("DASHBOARD_PASS")
    if env_user: config["dashboard_user"] = env_user
    if env_pass: config["dashboard_pass"] = env_pass

    # Handle legacy env vars for initial setup if no domains exist
    env_domain = os.environ.get("DDNS_DOMAIN")
    env_url = os.environ.get("UPDATE_URL")
    if env_domain and env_url and not config["domains"]:
        config["domains"].append({"domain": env_domain, "update_url": env_url})

def save_config():
    try:
        data_dir = os.path.dirname(CONFIG_PATH)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            
        # Write to a temporary file first and then rename to ensure atomicity
        temp_path = CONFIG_PATH + ".tmp"
        with open(temp_path, 'w') as f:
            json.dump(config, f, indent=4)
        os.replace(temp_path, CONFIG_PATH)
    except Exception as e:
        print(f"CRITICAL ERROR in save_config: {e}")
        # Re-raise to be caught by route handlers
        raise e

load_config()

# Auth Helpers
def check_auth(username, password):
    return username == config.get("dashboard_user") and password == config.get("dashboard_pass")

def authenticate():
    return jsonify({"message": "Authentication Required"}), 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}

from functools import wraps
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Afraid IP Sync Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Roboto+Mono&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        :root {
            --primary-color: #2196F3;
            --primary-light: #BBDEFB;
            --primary-dark: #1976D2;
            --accent-color: #FF4081;
            --bg-color: #f5f5f5;
            --surface-color: #ffffff;
            --secondary-bg: #fafafa;
            --border-color: #eeeeee;
            --text-primary: #212121;
            --text-secondary: #757575;
            --error-color: #F44336;
            --success-color: #4CAF50;
            --warning-color: #FF9800;
            --shadow: 0 2px 4px rgba(0,0,0,0.1), 0 4px 12px rgba(0,0,0,0.05);
            --input-bg: #ffffff;
            --input-border: #dddddd;
            
            /* Status Colors */
            --status-success-bg: #E8F5E9;
            --status-success-text: #2E7D32;
            --status-warning-bg: #FFF3E0;
            --status-warning-text: #EF6C00;
            --status-error-bg: #FFEBEE;
            --status-error-text: #C62828;
            --status-info-bg: #E3F2FD;
            --status-info-text: #1565C0;
        }

        .dark-theme {
            --bg-color: #121212;
            --surface-color: #1e1e1e;
            --secondary-bg: #2c2c2c;
            --border-color: #333333;
            --text-primary: #ffffff;
            --text-secondary: #b0b0b0;
            --shadow: 0 4px 20px rgba(0,0,0,0.5);
            --input-bg: #2c2c2c;
            --input-border: #444444;

            /* Dark Mode Status Colors - Desaturated and high contrast */
            --status-success-bg: rgba(76, 175, 80, 0.15);
            --status-success-text: #81C784;
            --status-warning-bg: rgba(255, 152, 0, 0.15);
            --status-warning-text: #FFB74D;
            --status-error-bg: rgba(244, 67, 54, 0.15);
            --status-error-text: #E57373;
            --status-info-bg: rgba(33, 150, 243, 0.15);
            --status-info-text: #64B5F6;
        }

        body { 
            font-family: 'Roboto', sans-serif; 
            margin: 0; 
            background: var(--bg-color); 
            color: var(--text-primary);
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }

        .app-bar {
            background: var(--primary-dark);
            color: white;
            padding: 0 24px;
            height: 64px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .app-title {
            font-size: 20px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .container {
            max-width: 1000px;
            margin: 24px auto;
            width: 95%;
            flex-grow: 1;
        }

        .card { 
            background: var(--surface-color); 
            border-radius: 8px; 
            box-shadow: var(--shadow); 
            margin-bottom: 24px; 
            overflow: hidden;
            transition: transform 0.2s;
        }

        .card-header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .card-title {
            font-size: 18px;
            font-weight: 500;
            color: var(--primary-dark);
        }

        .table-container {
            width: 100%;
            overflow-x: auto;
        }

        table { 
            width: 100%; 
            border-collapse: collapse;
        }

        th { 
            text-align: left; 
            padding: 12px 24px; 
            background: var(--secondary-bg);
            color: var(--text-secondary);
            font-size: 12px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 2px solid var(--border-color);
        }

        td { 
            padding: 16px 24px;
            border-bottom: 1px solid var(--border-color);
            font-size: 14px;
        }

        .monospace { font-family: 'Roboto Mono', monospace; font-size: 13px; }

        .status-badge { 
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px; 
            border-radius: 16px; 
            font-weight: 500; 
            font-size: 12px; 
        }

        .success { background: var(--status-success-bg); color: var(--status-success-text); }
        .warning { background: var(--status-warning-bg); color: var(--status-warning-text); }
        .error { background: var(--status-error-bg); color: var(--status-error-text); }
        .info { background: var(--status-info-bg); color: var(--status-info-text); }

        .btn { 
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 0 16px;
            height: 36px;
            border-radius: 4px;
            text-transform: uppercase;
            font-size: 14px;
            font-weight: 500;
            letter-spacing: 0.5px;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
            text-decoration: none;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .btn-primary { background: var(--primary-color); color: white; }
        .btn-primary:hover { background: var(--primary-dark); box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
        .btn-secondary { background: var(--surface-color); color: var(--primary-color); border: 1px solid var(--border-color); }
        .btn-secondary:hover { background: var(--secondary-bg); }
        .btn-warning { background: var(--warning-color); color: white; }
        .btn-warning:hover { filter: brightness(0.9); }
        
        .fab {
            position: fixed;
            bottom: 24px;
            right: 24px;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: var(--accent-color);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            text-decoration: none;
            transition: transform 0.2s;
        }
        .fab:hover { transform: scale(1.1); }

        .empty-state { text-align: center; padding: 48px; color: var(--text-secondary); }
        .footer { padding: 24px; font-size: 13px; color: var(--text-secondary); text-align: center; }
        
        .alert { 
            padding: 12px 24px;
            margin-bottom: 24px;
            border-radius: 4px;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .alert-success { background: var(--success-color); color: white; }
        .alert-error { background: var(--error-color); color: white; }
        .alert-warning { background: var(--warning-color); color: white; }
        .alert-info { background: var(--primary-color); color: white; }

        @keyframes fadeOut {
            from { opacity: 1; transform: translateY(0); }
            to { opacity: 0; transform: translateY(-10px); }
        }
        .alert.hiding {
            animation: fadeOut 0.5s ease-in forwards;
        }

        .ip-container { display: flex; flex-direction: column; gap: 4px; }
        .ip-label { font-size: 10px; color: var(--text-secondary); font-weight: bold; }
    </style>
</head>
<body class="{{ config.theme }}-theme">
    <header class="app-bar">
        <div class="app-title">
            <span class="material-icons">sync</span>
            Afraid IP Sync
        </div>
        <div class="app-actions">
            <a href="{{ url_for('settings') }}" class="btn btn-secondary">
                <span class="material-icons" style="font-size: 18px;">settings</span>
                Settings
            </a>
        </div>
    </header>

    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }}">
                <span class="material-icons">
                  {% if category == 'success' %}check_circle
                  {% elif category == 'error' %}error
                  {% elif category == 'warning' %}warning
                  {% else %}info{% endif %}
                </span>
                {{ message }}
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <div class="card">
            <div class="card-header">
                <div class="card-title">Monitored Domains</div>
                <div style="display: flex; gap: 8px;">
                    <form action="{{ url_for('sync_all') }}" method="POST" style="margin: 0;">
                        <button type="submit" class="btn btn-primary">
                            <span class="material-icons" style="font-size: 18px;">refresh</span>
                            Sync Now
                        </button>
                    </form>
                </div>
            </div>

            {% if not config.domains %}
            <div class="empty-state">
                <span class="material-icons" style="font-size: 48px; margin-bottom: 16px;">dns</span>
                <p>No domains configured yet.</p>
                <a href="{{ url_for('settings') }}" class="btn btn-primary">Setup Domains</a>
            </div>
            {% else %}
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Domain</th>
                            <th>IP Status</th>
                            <th>Status Message</th>
                            <th>Last Check</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for d in config.domains %}
                        {% set res = state.results[d.domain] or {} %}
                        <tr>
                            <td>
                                <div style="font-weight: 500;">{{ d.domain }}</div>
                            </td>
                            <td>
                                <div class="ip-container">
                                    <div class="monospace"><span class="ip-label">EXT:</span> <span data-domain="{{ d.domain }}" data-field="external_ip">{{ res.external_ip or '...' }}</span></div>
                                    <div class="monospace"><span class="ip-label">DNS:</span> <span data-domain="{{ d.domain }}" data-field="dns_ip">{{ res.dns_ip or '...' }}</span></div>
                                </div>
                            </td>
                            <td>
                                <span class="status-badge {{ res.status_class or 'info' }}" data-domain="{{ d.domain }}" data-field="status_badge">
                                    <span class="material-icons" style="font-size: 14px;">
                                        {{ 'check' if res.status_class == 'success' else 'warning' if res.status_class == 'warning' else 'error' if res.status_class == 'error' else 'schedule' }}
                                    </span>
                                    {{ res.status or 'Waiting' }}
                                </span>
                            </td>
                            <td style="color: var(--text-secondary); font-size: 12px;" data-domain="{{ d.domain }}" data-field="last_check">
                                {{ res.last_check or 'Never' }}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
        </div>
        
        <script>
            function updateStatus() {
                fetch('/api/status')
                    .then(response => response.json())
                    .then(data => {
                        for (const domain in data) {
                            const res = data[domain];
                            
                            // Update IP elements
                            const extIp = document.querySelector(`[data-domain="${domain}"][data-field="external_ip"]`);
                            const dnsIp = document.querySelector(`[data-domain="${domain}"][data-field="dns_ip"]`);
                            if (extIp) extIp.textContent = res.external_ip || '...';
                            if (dnsIp) dnsIp.textContent = res.dns_ip || '...';

                            // Update Status Badge
                            const badge = document.querySelector(`[data-domain="${domain}"][data-field="status_badge"]`);
                            if (badge) {
                                badge.className = `status-badge ${res.status_class || 'info'}`;
                                const icon = badge.querySelector('.material-icons');
                                const textNode = Array.from(badge.childNodes).find(node => node.nodeType === Node.TEXT_NODE);
                                
                                if (icon) {
                                    icon.textContent = res.status_class === 'success' ? 'check' : 
                                                      res.status_class === 'warning' ? 'warning' : 
                                                      res.status_class === 'error' ? 'error' : 'schedule';
                                }
                                if (textNode) textNode.textContent = ' ' + (res.status || 'Waiting');
                            }

                            // Update Last Check
                            const lastCheck = document.querySelector(`[data-domain="${domain}"][data-field="last_check"]`);
                            if (lastCheck) lastCheck.textContent = res.last_check || 'Never';
                        }
                    })
                    .catch(err => console.error('Error fetching status:', err));
            }

            // Poll every 5 seconds
            setInterval(updateStatus, 5000);
        </script>

    <script>
        // Auto-hide alerts after 5 seconds
        document.addEventListener('DOMContentLoaded', () => {
            const alerts = document.querySelectorAll('.alert');
            alerts.forEach(alert => {
                setTimeout(() => {
                    alert.classList.add('hiding');
                    setTimeout(() => alert.remove(), 500);
                }, 5000);
            });
        });
    </script>
        
        <div style="text-align: right;">
            <form action="{{ url_for('force_all') }}" method="POST">
                <button type="submit" class="btn btn-warning">
                    <span class="material-icons" style="font-size: 18px;">bolt</span>
                    Force Correct All
                </button>
            </form>
        </div>

        <div class="footer">
            Automatic checks every {{ config.global_interval }}s • Timezone: {{ config.timezone }}
        </div>
    </div>
</body>
</html>
"""

SETTINGS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Settings - Afraid IP Sync</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Roboto+Mono&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        :root {
            --primary-color: #2196F3;
            --primary-dark: #1976D2;
            --bg-color: #f5f5f5;
            --surface-color: #ffffff;
            --secondary-bg: #fafafa;
            --border-color: #eeeeee;
            --text-primary: #212121;
            --text-secondary: #757575;
            --shadow: 0 2px 4px rgba(0,0,0,0.1);
            --input-bg: #ffffff;
            --input-border: #dddddd;

            /* Status Colors */
            --status-success-bg: #E8F5E9;
            --status-success-text: #2E7D32;
            --status-warning-bg: #FFF3E0;
            --status-warning-text: #EF6C00;
            --status-error-bg: #FFEBEE;
            --status-error-text: #C62828;
            --status-info-bg: #E3F2FD;
            --status-info-text: #1565C0;
        }

        .dark-theme {
            --bg-color: #121212;
            --surface-color: #1e1e1e;
            --secondary-bg: #2c2c2c;
            --border-color: #333333;
            --text-primary: #ffffff;
            --text-secondary: #b0b0b0;
            --shadow: 0 4px 20px rgba(0,0,0,0.5);
            --input-bg: #2c2c2c;
            --input-border: #444444;

            /* Dark Mode Status Colors */
            --status-success-bg: rgba(76, 175, 80, 0.15);
            --status-success-text: #81C784;
            --status-warning-bg: rgba(255, 152, 0, 0.15);
            --status-warning-text: #FFB74D;
            --status-error-bg: rgba(244, 67, 54, 0.15);
            --status-error-text: #E57373;
            --status-info-bg: rgba(33, 150, 243, 0.15);
            --status-info-text: #64B5F6;
        }
        .alert-success { background: var(--status-success-text); color: white; }
        .alert-error { background: var(--status-error-text); color: white; }
        .alert-warning { background: var(--status-warning-text); color: white; }
        .alert-info { background: var(--status-info-text); color: white; }

        @keyframes fadeOut {
            from { opacity: 1; transform: translateY(0); }
            to { opacity: 0; transform: translateY(-10px); }
        }
        .alert.hiding {
            animation: fadeOut 0.5s ease-in forwards;
        }

        body { font-family: 'Roboto', sans-serif; margin: 0; background: var(--bg-color); color: var(--text-primary); }
        
        .app-bar {
            background: var(--primary-dark);
            color: white;
            padding: 0 24px;
            height: 64px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }

        .container { max-width: 800px; margin: 24px auto; width: 95%; }

        .card { 
            background: var(--surface-color); 
            border-radius: 8px; 
            box-shadow: var(--shadow); 
            padding: 32px; 
            margin-bottom: 24px; 
        }

        .section-title { 
            font-size: 18px; 
            font-weight: 500; 
            color: var(--primary-dark);
            margin: 0 0 24px 0;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 12px;
        }

        .input-group { margin-bottom: 20px; }
        .label { display: block; font-size: 12px; font-weight: 500; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase; }
        
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid var(--input-border);
            background: var(--input-bg);
            color: var(--text-primary);
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
            transition: border-color 0.2s;
        }
        input:focus { border-color: var(--primary-color); outline: none; }

        .btn { 
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 0 24px;
            height: 40px;
            border-radius: 4px;
            text-transform: uppercase;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            border: none;
            text-decoration: none;
            transition: 0.2s;
        }
        .btn-primary { background: var(--primary-color); color: white; }
        .btn-secondary { background: var(--secondary-bg); color: var(--text-primary); border: 1px solid var(--border-color); }
        .btn-success { background: var(--status-success-text); color: white; }
        .btn-danger { background: var(--status-error-text); color: white; padding: 0 12px; height: 32px; }

        .domain-item { 
            display: flex; 
            align-items: center; 
            padding: 16px; 
            background: var(--secondary-bg);
            border-radius: 4px;
            margin-bottom: 8px;
            border: 1px solid var(--border-color);
        }
        
        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
        
        @media (max-width: 600px) {
            .row { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body class="{{ config.theme }}-theme">
    <header class="app-bar">
        <div style="display: flex; align-items: center; gap: 12px; font-size: 18px; font-weight: 500;">
            <a href="{{ url_for('home') }}" style="color: white; text-decoration: none; display: flex;"><span class="material-icons">arrow_back</span></a>
            Settings
        </div>
    </header>

    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }}">
                <span class="material-icons">
                  {% if category == 'success' %}check_circle
                  {% elif category == 'error' %}error
                  {% elif category == 'warning' %}warning
                  {% else %}info{% endif %}
                </span>
                {{ message }}
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <div class="card">
            <div class="section-title">
                <span class="material-icons">security</span>
                Dashboard Security
            </div>
            <form action="{{ url_for('save_security') }}" method="POST">
                <div class="row">
                    <div class="input-group">
                        <span class="label">Dashboard Username</span>
                        <input type="text" name="dashboard_user" value="{{ config.dashboard_user }}">
                    </div>
                    <div class="input-group">
                        <span class="label">Dashboard Password</span>
                        <input type="password" name="dashboard_pass" value="{{ config.dashboard_pass }}">
                    </div>
                </div>
                <button type="submit" class="btn btn-secondary">Update Security</button>
                <div style="font-size: 11px; color: var(--text-secondary); margin-top: 12px;">
                    <em>Note: Changing credentials will require a new login.</em>
                </div>
            </form>

            <div class="section-title" style="margin-top: 48px;">
                <span class="material-icons">account_circle</span>
                Afraid.org Account
            </div>
            <form action="{{ url_for('save_account') }}" method="POST">
                <div class="row">
                    <div class="input-group">
                        <span class="label">Username</span>
                        <input type="text" name="afraid_user" value="{{ config.afraid_user }}">
                    </div>
                    <div class="input-group">
                        <span class="label">Password</span>
                        <input type="password" name="afraid_pass" value="{{ config.afraid_pass }}">
                    </div>
                </div>
                <div style="display: flex; gap: 12px;">
                    <button type="submit" class="btn btn-secondary">Save Credentials</button>
                    <button formaction="{{ url_for('import_afraid') }}" class="btn btn-success">
                        <span class="material-icons" style="font-size: 18px;">download</span>
                        Import All Domains
                    </button>
                </div>
            </form>

            <div class="section-title" style="margin-top: 48px;">
                <span class="material-icons">list</span>
                Monitored Domains
            </div>
            {% for d in config.domains %}
            <div class="domain-item">
                <div style="flex-grow: 1;">
                    <div style="font-weight: 500;">{{ d.domain }}</div>
                    <div style="font-size: 11px; color: var(--text-secondary); word-break: break-all;">{{ d.update_url }}</div>
                </div>
                <form action="{{ url_for('delete_domain', index=loop.index0) }}" method="POST">
                    <button type="submit" class="btn btn-danger">Delete</button>
                </form>
            </div>
            {% endfor %}

            <div class="card-inner" style="background: var(--secondary-bg); padding: 20px; border-radius: 4px; margin-top: 24px;">
                <div style="font-weight: 500; margin-bottom: 16px;">Add Domain Manually</div>
                <form action="{{ url_for('add_domain') }}" method="POST">
                    <div class="row">
                        <div class="input-group">
                            <span class="label">Domain</span>
                            <input type="text" name="domain" required>
                        </div>
                        <div class="input-group">
                            <span class="label">Token URL</span>
                            <input type="text" name="update_url" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">Add Domain</button>
                </form>
            </div>

            <div class="section-title" style="margin-top: 48px;">
                <span class="material-icons">settings_applications</span>
                Global Configuration
            </div>
            <form action="{{ url_for('save_global') }}" method="POST">
                <div class="row">
                    <div class="input-group">
                        <span class="label">Check Interval (seconds)</span>
                        <input type="number" name="global_interval" value="{{ config.global_interval }}">
                    </div>
                    <div class="input-group">
                        <span class="label">Timezone</span>
                        <input type="text" name="timezone" value="{{ config.timezone }}">
                    </div>
                </div>
                <div class="input-group">
                    <span class="label">Theme</span>
                    <select name="theme" style="width: 100%; padding: 12px; border: 1px solid var(--border-color); border-radius: 4px; font-size: 16px; background: var(--input-bg); color: var(--text-primary);">
                        <option value="light" {{ 'selected' if config.theme == 'light' }}>Light Mode</option>
                        <option value="dark" {{ 'selected' if config.theme == 'dark' }}>Dark Mode</option>
                    </select>
                </div>
                <button type="submit" class="btn btn-secondary">Update Config</button>
            </form>
        </div>
    </div>
    <script>
        // Auto-hide alerts after 5 seconds
        document.addEventListener('DOMContentLoaded', () => {
            const alerts = document.querySelectorAll('.alert');
            alerts.forEach(alert => {
                setTimeout(() => {
                    alert.classList.add('hiding');
                    setTimeout(() => alert.remove(), 500);
                }, 5000);
            });
        });
    </script>
</body>
</html>
"""

def get_external_ip():
    # Try multiple services to ensure reliability and plain text output
    services = [
        ["curl", "-s", "https://ident.me"],
        ["curl", "-s", "https://ifconfig.me/ip"],
        ["curl", "-s", "https://icanhazip.com"]
    ]
    
    for cmd in services:
        try:
            output = subprocess.check_output(cmd, text=True, timeout=10).strip()
            # Basic validation: ensure it looks like an IP (doesn't contain HTML)
            if output and "<" not in output and ">" not in output and len(output) < 50:
                return output
        except Exception:
            continue
    return None

def get_dns_ip(domain):
    try:
        result = subprocess.check_output(["dig", "+short", domain], text=True).strip()
        return result.split('\n')[0] if result else None
    except Exception:
        return None

def update_ddns(url):
    # Self-healing: Detect and repair double-prefixed URLs
    # Example: https://sync.afraid.org/u/http://freedns.afraid.org/...
    if "sync.afraid.org/u/http" in url:
        # Extract the actual URL from the mangled string
        parts = url.split("sync.afraid.org/u/")
        if len(parts) > 1:
            url = parts[1]
    
    try:
        # Use -f to return an error code on 4xx/5xx responses
        # Add -L to follow redirects
        cmd = ["curl", "-s", "-L", "-w", "\n%{http_code}", "-A", "AfraidIPSync/1.0", url]
        output = subprocess.check_output(cmd, text=True, timeout=15).strip().split('\n')
        
        status_code = output[-1] if len(output) > 1 else "Unknown"
        body = "\n".join(output[:-1]) if len(output) > 1 else output[0]
        
        if status_code == "200":
            return body if body.strip() else "OK (Empty Response)"
        elif status_code == "404":
            return f"Error 404: Page not found (URL: {url})"
        else:
            return f"Status {status_code}: {body.strip()[:100]}"
    except subprocess.TimeoutExpired:
        return "Error: Update request timed out"
    except Exception as e:
        return f"Error: {str(e)}"

def get_now_str():
    try:
        tz_name = str(config.get("timezone", "UTC"))
        tz = ZoneInfo(tz_name)
        return datetime.now(tz).strftime("%H:%M:%S")
    except Exception:
        return datetime.now().strftime("%H:%M:%S")

def run_single_check(domain_config: Dict[str, str], force: bool = False) -> None:
    domain = domain_config.get("domain")
    update_url = domain_config.get("update_url")
    
    if not domain: return

    # Ensure result structure exists for this domain
    results_dict: Dict[str, Any] = state.get("results", {})
    if domain not in results_dict:
        results_dict[domain] = {
            "external_ip": "...",
            "dns_ip": "...",
            "status": "Waiting",
            "status_class": "info",
            "last_check": "Never"
        }
        
    res = results_dict[domain]
    ext_ip = get_external_ip()
    res["external_ip"] = ext_ip or "Error"
    
    dns_ip = get_dns_ip(domain)
    res["dns_ip"] = dns_ip or "Not found"
    
    if not force and ext_ip and ext_ip == dns_ip:
        res["status"] = "Synced"
        res["status_class"] = "success"
    elif ext_ip:
        if force:
            res["status"] = "Correcting..."
        else:
            res["status"] = "Mismatch"
        
        res["status_class"] = "warning"
        
        if update_url:
            update_res = update_ddns(update_url)
            res["status"] = f"Updated: {update_res}"
        else:
            res["status"] = "No URL"
    else:
        res["status"] = "IP Error"
        res["status_class"] = "error"
        
    res["last_check"] = get_now_str()
    results_dict[domain] = res

def run_all_checks(force: bool = False) -> None:
    domains_list: List[Dict[str, str]] = config.get("domains", [])
    for d in domains_list:
        run_single_check(d, force=force)

def check_loop() -> None:
    while True:
        run_all_checks()
        global_interval = config.get("global_interval", 1800)
        interval = float(global_interval) if isinstance(global_interval, (int, float)) else 1800.0
        time.sleep(interval)

@app.route('/')
@requires_auth
def home():
    return render_template_string(HTML_TEMPLATE, state=state, config=config)

@app.route('/api/status')
@requires_auth
def api_status():
    return jsonify(state["results"])

@app.route('/settings')
@requires_auth
def settings():
    safe_config = config.copy()
    
    if safe_config.get("afraid_pass"):
        safe_config["afraid_pass"] = "********"
    if safe_config.get("dashboard_pass"):
        safe_config["dashboard_pass"] = "********"
        
    safe_domains = []
    for d in safe_config.get("domains", []):
        d_safe = d.copy()
        url = d_safe.get("update_url", "")
        if "sync.afraid.org/u/" in url:
            parts = url.split("sync.afraid.org/u/")
            if len(parts) == 2:
                token_part = parts[1].split("/")
                if len(token_part) > 2: # Has trailing query or slashed parts
                     d_safe["update_url"] = f"https://sync.afraid.org/u/********/{token_part[-1]}"
                elif len(token_part) > 0:
                     d_safe["update_url"] = f"https://sync.afraid.org/u/********/"
        safe_domains.append(d_safe)
    safe_config["domains"] = safe_domains

    return render_template_string(SETTINGS_TEMPLATE, config=safe_config)

@app.route('/save_security', methods=['POST'])
@requires_auth
def save_security():
    try:
        new_user = request.form.get("dashboard_user", "").strip()
        new_pass = request.form.get("dashboard_pass", "").strip()
        
        if new_user:
            config["dashboard_user"] = new_user
        if new_pass and new_pass != "********":
            config["dashboard_pass"] = new_pass
            
        save_config()
        flash("Dashboard security updated.", "success")
    except Exception as e:
        flash(f"Error saving security: {str(e)}", "error")
    return redirect(url_for('settings'))

@app.route('/save_account', methods=['POST'])
@requires_auth
def save_account():
    try:
        new_user = request.form.get("afraid_user", "").strip()
        new_pass = request.form.get("afraid_pass", "").strip()
        
        config["afraid_user"] = new_user
        if new_pass != "********":
            config["afraid_pass"] = new_pass
            
        save_config()
        flash("Account credentials saved.", "success")
    except Exception as e:
        flash(f"Error saving account: {str(e)}", "error")
    return redirect(url_for('settings'))

@app.route('/import_afraid', methods=['POST'])
@requires_auth
def import_afraid():
    user = config.get("afraid_user")
    pw = config.get("afraid_pass")
    
    if not user or not pw:
        flash("Please enter Afraid.org credentials first.", "error")
        return redirect(url_for('settings'))
    
    sha_hash = hashlib.sha1(f"{user}|{pw}".encode()).hexdigest()
    api_url = f"http://freedns.afraid.org/api/?action=getdyndns&sha={sha_hash}"
    
    try:
        data = subprocess.check_output(["curl", "-s", api_url], text=True)
        if "Authentication Failed" in data:
            flash("Afraid.org Authentication Failed. Check credentials.", "error")
            return redirect(url_for('settings'))
        
        lines = data.strip().split('\n')
        imported_count = 0
        for line in lines:
            parts = line.split('|')
            if len(parts) >= 3:
                domain_name = str(parts[0]).strip()
                api_token_or_url = str(parts[2]).strip()
                
                # Check if it's already a full URL or contains a URL
                if "://" in api_token_or_url:
                    # If it's a full URL, use it directly
                    # Sometimes the API returns a URL that starts with http or contains it
                    if api_token_or_url.startswith("http"):
                        update_url = api_token_or_url
                    else:
                        # Fallback for weirdly formatted strings that contain a URL
                        # (though unlikely from Afraid API, let's be safe)
                        start_idx = api_token_or_url.find("http")
                        update_url = api_token_or_url[start_idx:] if start_idx != -1 else api_token_or_url
                else:
                    # It's just a token, use the sync.afraid.org format
                    token = api_token_or_url.strip('/')
                    update_url = f"https://sync.afraid.org/u/{token}/"
                
                exists = False
                domains_list: List[Dict[str, str]] = config.get("domains", [])
                for d in domains_list:
                    if d.get("domain") == domain_name:
                        d["update_url"] = update_url
                        exists = True
                        break
                if not exists:
                    domains_list.append({"domain": domain_name, "update_url": update_url})
                imported_count = imported_count + 1
        
        save_config()
        flash(f"Successfully imported/updated {imported_count} domains from Afraid.org.", "success")
    except Exception as e:
        flash(f"Import failed: {str(e)}", "error")
        
    return redirect(url_for('settings'))

@app.route('/add_domain', methods=['POST'])
@requires_auth
def add_domain():
    try:
        domain = request.form.get("domain", "").strip()
        update_url = request.form.get("update_url", "").strip()
        if domain and update_url:
            for d in config["domains"]:
                if d["domain"] == domain:
                    d["update_url"] = update_url
                    save_config()
                    flash(f"Updated {domain}.", "success")
                    return redirect(url_for('settings'))
            
            config["domains"].append({"domain": domain, "update_url": update_url})
            save_config()
            flash(f"Added {domain}.", "success")
    except Exception as e:
        flash(f"Error adding domain: {str(e)}", "error")
    return redirect(url_for('settings'))

@app.route('/delete_domain/<int:index>', methods=['POST'])
@requires_auth
def delete_domain(index: int):
    domains_list: List[Dict[str, str]] = config.get("domains", [])
    if 0 <= index < len(domains_list):
        domain = domains_list[index].get("domain")
        if domain:
            results_dict: Dict[str, Any] = state.get("results", {})
            if domain in results_dict:
                results_dict.pop(domain, None)
            domains_list.pop(index)
            save_config()
            flash(f"Deleted {domain}.", "success")
    return redirect(url_for('settings'))

@app.route('/save_global', methods=['POST'])
@requires_auth
def save_global():
    try:
        config["global_interval"] = int(request.form.get("global_interval", 1800))
        config["timezone"] = request.form.get("timezone", "UTC").strip()
        config["theme"] = request.form.get("theme", "light").strip()
        save_config()
        flash("Global settings saved.", "success")
    except Exception as e:
        flash(f"Error saving global configuration: {str(e)}", "error")
    return redirect(url_for('settings'))

@app.route('/sync_all', methods=['POST'])
@requires_auth
def sync_all():
    run_all_checks(force=False)
    flash("Sync initiated for all domains.", "info")
    return redirect(url_for('home'))

@app.route('/force_all', methods=['POST'])
@requires_auth
def force_all():
    run_all_checks(force=True)
    flash("Force correction initiated for all domains.", "warning")
    return redirect(url_for('home'))

if __name__ == "__main__":
    Thread(target=check_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7777)
