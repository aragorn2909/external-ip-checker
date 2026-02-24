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
app.secret_key = os.urandom(24)

CONFIG_PATH = os.path.join("/app/data", "config.json")

# Default config
default_config: Dict[str, Any] = {
    "domains": [],
    "global_interval": 1800,
    "afraid_user": "",
    "afraid_pass": "",
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
                if not isinstance(config.get("timezone"), str): config["timezone"] = "UTC"
                if not isinstance(config.get("theme"), str): config["theme"] = "light"
        except Exception as e:
            print(f"Error loading config: {e}")

def save_config():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)

load_config()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Afraid IP Sync Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
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
              <div class="alert alert-{{ 'success' if category == 'success' else 'error' }}">
                <span class="material-icons">{{ 'check_circle' if category == 'success' else 'error' }}</span>
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
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
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
        <div class="card">
            <div class="section-title">
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
</body>
</html>
"""

def get_external_ip():
    try:
        return subprocess.check_output(["curl", "-s", "https://ifconfig.me"], text=True).strip()
    except Exception:
        return None

def get_dns_ip(domain):
    try:
        result = subprocess.check_output(["dig", "+short", domain], text=True).strip()
        return result.split('\n')[0] if result else None
    except Exception:
        return None

def update_ddns(url):
    try:
        return subprocess.check_output(["curl", "-s", url], text=True).strip()
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
def home():
    return render_template_string(HTML_TEMPLATE, state=state, config=config)

@app.route('/api/status')
def api_status():
    return jsonify(state["results"])

@app.route('/settings')
def settings():
    return render_template_string(SETTINGS_TEMPLATE, config=config)

@app.route('/save_account', methods=['POST'])
def save_account():
    config["afraid_user"] = request.form.get("afraid_user", "").strip()
    config["afraid_pass"] = request.form.get("afraid_pass", "").strip()
    save_config()
    flash("Account credentials saved.", "success")
    return redirect(url_for('settings'))

@app.route('/import_afraid', methods=['POST'])
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
                domain_name = str(parts[0])
                update_token = str(parts[2])
                update_url = f"https://sync.afraid.org/u/{update_token}/"
                
                exists = False
                # config["domains"] is guaranteed to be List[Dict[str, str]] by load_config
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
def add_domain():
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
    return redirect(url_for('settings'))

@app.route('/delete_domain/<int:index>', methods=['POST'])
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
def save_global():
    try:
        config["global_interval"] = int(request.form.get("global_interval", 1800))
        config["timezone"] = request.form.get("timezone", "UTC").strip()
        config["theme"] = request.form.get("theme", "light").strip()
        save_config()
        flash("Global settings saved.", "success")
    except ValueError:
        pass
    return redirect(url_for('settings'))

@app.route('/sync_all', methods=['POST'])
def sync_all():
    run_all_checks(force=False)
    flash("Sync initiated for all domains.", "success")
    return redirect(url_for('home'))

@app.route('/force_all', methods=['POST'])
def force_all():
    run_all_checks(force=True)
    flash("Force correction initiated for all domains.", "success")
    return redirect(url_for('home'))

if __name__ == "__main__":
    Thread(target=check_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7777)
