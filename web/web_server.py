#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Review Gate V2 - Web Server Component
Provides a web-based interface for Review Gate, eliminating the need for VSCode extension.

This module runs alongside the MCP server and provides:
- WebSocket-based real-time communication
- Modern responsive UI
- Image upload support
- Auto-launch browser on startup

Author: Lakshman Turlapati (Original), Extended for Web Support
"""

import asyncio
import json
import os
import sys
import logging
import webbrowser
import threading
import time
import base64
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, Set, List
from dataclasses import dataclass, field

# Import message storage
from message_store import MessageStorage, MessageRecord

# Fix Windows console encoding for Chinese characters
if sys.platform == 'win32':
    try:
        import codecs
        # Set stdout/stderr to UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# aiohttp will be imported when needed
AIOHTTP_AVAILABLE = False
try:
    from aiohttp import web
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    # aiohttp not available - create dummy web module for type hints
    class DummyWeb:
        Application = object
        AppRunner = object
        TCPSite = object
        WebSocketResponse = object
        WSMsgType = object
    web = DummyWeb()
    aiohttp = None
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_WEB_PORT = 8765
DEFAULT_HOST = "127.0.0.1"

# User settings file path
def get_settings_file_path() -> str:
    """Get the path to the user settings file"""
    if os.name == 'nt':  # Windows
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        settings_dir = os.path.join(app_data, 'ReviewGateV2')
    else:  # macOS and Linux
        settings_dir = os.path.expanduser('~/.config/review-gate-v2')
    
    os.makedirs(settings_dir, exist_ok=True)
    return os.path.join(settings_dir, 'settings.json')

def load_user_settings() -> Dict[str, Any]:
    """Load user settings from local file"""
    settings_file = get_settings_file_path()
    default_settings = {
        'timeout': 300,
        'auto_message': '继续',
        'theme': 'dark'
    }
    
    try:
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
                # Merge with defaults
                default_settings.update(saved_settings)
    except Exception as e:
        logger.warning(safe_log(f"Failed to load settings: {e}"))
    
    return default_settings

def save_user_settings(settings: Dict[str, Any]) -> bool:
    """Save user settings to local file"""
    settings_file = get_settings_file_path()
    
    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(safe_log(f"Failed to save settings: {e}"))
        return False


def safe_log(message: str) -> str:
    """Safely encode message for logging on Windows"""
    if sys.platform == 'win32':
        try:
            return message.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        except Exception:
            return message.encode('ascii', errors='replace').decode('ascii', errors='replace')
    return message


@dataclass
class WebServerConfig:
    """Configuration for the web server"""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_WEB_PORT
    auto_open_browser: bool = True
    timeout_duration: int = 300  # 5 minutes default
    show_countdown: bool = True


@dataclass
class PendingRequest:
    """Represents a pending review request"""
    trigger_id: str
    message: str
    title: str
    context: str
    urgent: bool
    timestamp: str
    tool: str
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_event_loop().create_future())


class ReviewGateWebServer:
    """Web server for Review Gate V2"""
    
    def __init__(self, config: Optional[WebServerConfig] = None):
        self.config = config or WebServerConfig()
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.websockets: Set[web.WebSocketResponse] = set()
        self.pending_requests: Dict[str, PendingRequest] = {}
        self.current_request: Optional[PendingRequest] = None
        self._running = False
        self._server_task: Optional[asyncio.Task] = None

        # Initialize message storage
        self.message_storage = MessageStorage()
        
    def get_html_content(self) -> str:
        """Generate the HTML content for the web interface"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Review Gate V2 - Web Interface</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            /* Dark Theme (Default) */
            --bg-primary: #1e1e1e;
            --bg-secondary: #252526;
            --bg-tertiary: #2d2d30;
            --text-primary: #cccccc;
            --text-secondary: #858585;
            --accent-orange: #ff6b35;
            --accent-green: #4ec9b0;
            --accent-blue: #569cd6;
            --border-color: #3c3c3c;
            --input-bg: #3c3c3c;
            --button-bg: #0e639c;
            --button-hover: #1177bb;
            --message-user-bg: #0e639c;
            --message-system-bg: #383838;
            --shadow-color: rgba(0, 0, 0, 0.3);
        }

        /* Light Theme */
        [data-theme="light"] {
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --bg-tertiary: #e9ecef;
            --text-primary: #212529;
            --text-secondary: #6c757d;
            --accent-orange: #fd7e14;
            --accent-green: #28a745;
            --accent-blue: #007bff;
            --border-color: #dee2e6;
            --input-bg: #ffffff;
            --button-bg: #007bff;
            --button-hover: #0056b3;
            --message-user-bg: #007bff;
            --message-system-bg: #f8f9fa;
            --shadow-color: rgba(0, 0, 0, 0.1);
        }

        /* Theme transition */
        * {
            transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .container {
            width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
            animation: slideIn 0.3s ease-out;
        }

        .content-wrapper {
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            padding: 0 24px;
        }

        @media (min-width: 1400px) {
            .content-wrapper {
                max-width: 1400px;
                padding: 0 40px;
            }
        }

        @media (min-width: 1800px) {
            .content-wrapper {
                max-width: 1600px;
                padding: 0 60px;
            }
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .header {
            flex-shrink: 0;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
        }

        .header-inner {
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        @media (min-width: 1400px) {
            .header-inner {
                max-width: 1400px;
                padding: 16px 40px;
            }
        }

        @media (min-width: 1800px) {
            .header-inner {
                max-width: 1600px;
                padding: 16px 60px;
            }
        }

        .header-actions {
            display: flex;
            gap: 8px;
            margin-left: auto;
        }

        .history-btn, .search-btn, .settings-btn, .theme-btn {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
        }

        .history-btn:hover, .search-btn:hover, .settings-btn:hover, .theme-btn:hover {
            background: var(--accent-blue);
            color: white;
            border-color: var(--accent-blue);
        }

        .theme-btn {
            padding: 6px 10px;
        }

        .theme-btn .fa-sun {
            color: #ffd700;
        }

        .theme-btn .fa-moon {
            color: #c0c0c0;
        }
        
        .header-title {
            font-size: 20px;
            font-weight: 600;
            color: var(--accent-orange);
        }
        
        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--accent-orange);
            animation: pulse 2s infinite;
        }
        
        .status-indicator.connected {
            background: var(--accent-green);
        }
        
        .status-indicator.disconnected {
            background: #f44336;
            animation: none;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .status-text {
            font-size: 12px;
            color: var(--text-secondary);
        }
        
        .countdown-container {
            display: none;
            align-items: center;
            gap: 8px;
            margin-left: auto;
            padding: 6px 14px;
            background: rgba(255, 107, 53, 0.1);
            border: 1px solid rgba(255, 107, 53, 0.3);
            border-radius: 16px;
        }
        
        .countdown-container.active {
            display: flex;
        }
        
        .countdown-label {
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
        }
        
        .countdown-time {
            font-size: 14px;
            font-weight: 600;
            color: var(--accent-orange);
            font-family: 'Consolas', monospace;
        }
        
        .countdown-time.warning {
            color: #f44336;
            animation: pulse 1s infinite;
        }
        
        .author {
            font-size: 11px;
            color: var(--text-secondary);
            margin-left: auto;
        }
        
        .messages-container {
            flex: 1;
            overflow-y: auto;
        }

        .messages-inner {
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        @media (min-width: 1400px) {
            .messages-inner {
                max-width: 1400px;
                padding: 20px 40px;
            }
        }

        @media (min-width: 1800px) {
            .messages-inner {
                max-width: 1600px;
                padding: 20px 60px;
            }
        }
        
        .message {
            display: flex;
            gap: 10px;
            animation: messageSlide 0.3s ease-out;
        }
        
        @keyframes messageSlide {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message.user {
            justify-content: flex-end;
        }
        
        .message-bubble {
            max-width: 70%;
            padding: 14px 18px;
            border-radius: 20px;
            word-wrap: break-word;
            white-space: pre-wrap;
            line-height: 1.6;
            font-size: 15px;
        }

        @media (min-width: 1200px) {
            .message-bubble {
                max-width: 65%;
            }
        }

        @media (min-width: 1600px) {
            .message-bubble {
                max-width: 60%;
            }
        }
        
        .message.system .message-bubble {
            background: var(--message-system-bg);
            border-bottom-left-radius: 6px;
        }
        
        .message.user .message-bubble {
            background: var(--message-user-bg);
            border-bottom-right-radius: 6px;
        }
        
        .message.system.plain {
            justify-content: center;
        }
        
        .message.system.plain .message-bubble {
            background: transparent;
            font-size: 13px;
            opacity: 0.8;
            font-style: italic;
            text-align: center;
            max-width: 100%;
        }
        
        .message-time {
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 6px;
        }
        
        .welcome-message {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-secondary);
        }
        
        .welcome-message h2 {
            color: var(--accent-orange);
            margin-bottom: 12px;
            font-size: 24px;
        }
        
        .welcome-message p {
            font-size: 14px;
            line-height: 1.6;
        }
        
        .input-container {
            flex-shrink: 0;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border-color);
        }

        .input-inner {
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        @media (min-width: 1400px) {
            .input-inner {
                max-width: 1400px;
                padding: 16px 40px;
            }
        }

        @media (min-width: 1800px) {
            .input-inner {
                max-width: 1600px;
                padding: 16px 60px;
            }
        }
        
        .input-container.disabled {
            opacity: 0.5;
            pointer-events: none;
        }
        
        .input-wrapper {
            flex: 1;
            display: flex;
            align-items: center;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 10px 16px;
            transition: all 0.2s ease;
            position: relative;
        }
        
        .input-wrapper:focus-within {
            border-color: var(--accent-orange);
            box-shadow: 0 0 0 2px rgba(255, 107, 53, 0.2);
        }
        
        
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        .message-input {
            flex: 1;
            background: transparent;
            border: none;
            outline: none;
            color: var(--text-primary);
            font-size: 14px;
            resize: none;
            min-height: 24px;
            max-height: 120px;
            padding-left: 28px;
            font-family: inherit;
            line-height: 1.5;
        }
        
        .message-input::placeholder {
            color: var(--text-secondary);
        }
        
        .attach-button, .send-button {
            background: none;
            border: none;
            color: var(--text-primary);
            cursor: pointer;
            padding: 8px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }
        
        .attach-button:hover {
            background: var(--bg-tertiary);
            color: var(--accent-orange);
        }
        
        .send-button {
            background: var(--button-bg);
            width: 40px;
            height: 40px;
        }
        
        .send-button:hover {
            background: var(--button-hover);
            transform: scale(1.05);
        }
        
        .send-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        /* Image preview */
        .image-preview {
            margin: 8px 0;
        }
        
        .image-preview img {
            max-width: 200px;
            max-height: 200px;
            border-radius: 8px;
            margin-top: 8px;
        }
        
        .image-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .image-filename {
            font-size: 12px;
            opacity: 0.9;
        }
        
        .remove-image-btn {
            background: rgba(255, 59, 48, 0.1);
            border: 1px solid rgba(255, 59, 48, 0.3);
            color: #ff3b30;
            border-radius: 50%;
            width: 22px;
            height: 22px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            transition: all 0.2s ease;
        }
        
        .remove-image-btn:hover {
            background: rgba(255, 59, 48, 0.2);
            transform: scale(1.1);
        }
        
        /* Drag and drop overlay */
        .drag-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 107, 53, 0.1);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .drag-overlay.active {
            display: flex;
        }
        
        .drag-overlay-content {
            background: var(--bg-secondary);
            padding: 24px 48px;
            border-radius: 12px;
            border: 2px dashed var(--accent-orange);
            text-align: center;
        }
        
        .drag-overlay-content i {
            font-size: 48px;
            color: var(--accent-orange);
            margin-bottom: 12px;
        }
        
        /* Responsive */
        @media (max-width: 1024px) {
            .header-inner,
            .messages-inner,
            .input-inner {
                padding-left: 20px;
                padding-right: 20px;
            }
        }

        @media (max-width: 768px) {
            .header-inner,
            .messages-inner,
            .input-inner {
                padding-left: 16px;
                padding-right: 16px;
            }
            
            .message-bubble {
                max-width: 88%;
            }
            
            .header-inner {
                flex-wrap: wrap;
                gap: 10px;
            }
            
            .header-left {
                flex: 1;
                min-width: 200px;
            }
            
            .header-right {
                flex-wrap: wrap;
            }
        }

        @media (max-width: 480px) {
            .header-inner,
            .messages-inner,
            .input-inner {
                padding-left: 12px;
                padding-right: 12px;
            }
            
            .message-bubble {
                max-width: 92%;
            }
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-primary);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-secondary);
        }
        
        /* Connection status banner */
        .connection-banner {
            display: none;
            padding: 8px 16px;
            background: rgba(244, 67, 54, 0.1);
            border-bottom: 1px solid rgba(244, 67, 54, 0.3);
            color: #f44336;
            font-size: 13px;
            text-align: center;
        }

        .connection-banner.visible {
            display: block;
        }

        .connection-banner.reconnecting {
            background: rgba(255, 152, 0, 0.1);
            border-color: rgba(255, 152, 0, 0.3);
            color: #ff9800;
        }

        /* History modal */
        .history-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 2000;
            align-items: center;
            justify-content: center;
            transition: background-color 0.3s ease;
        }

        [data-theme="light"] .history-modal {
            background: rgba(0, 0, 0, 0.3);
        }

        .history-modal.active {
            display: flex;
        }

        .history-content {
            background: var(--bg-primary);
            border-radius: 20px;
            width: 90%;
            max-width: 900px;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.3);
        }

        @media (min-width: 1200px) {
            .history-content {
                max-width: 1000px;
            }
        }

        @media (min-width: 1600px) {
            .history-content {
                max-width: 1100px;
            }
        }

        .history-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--bg-secondary);
        }

        .history-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--accent-orange);
        }

        .history-controls {
            display: flex;
            gap: 8px;
            align-items: center;
        }

        .date-selector {
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
        }

        .close-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 18px;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            transition: all 0.2s ease;
        }

        .close-btn:hover {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }

        .history-body {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }

        .search-section {
            margin-bottom: 16px;
            display: flex;
            gap: 8px;
        }

        .search-input {
            flex: 1;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
        }

        .search-input:focus {
            outline: none;
            border-color: var(--accent-orange);
        }

        .history-message {
            margin-bottom: 16px;
            padding: 16px 18px;
            background: rgba(255, 255, 255, 0.04);
            border-radius: 16px;
            border-left: 4px solid var(--accent-blue);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }

        [data-theme="light"] .history-message {
            background: rgba(0, 0, 0, 0.02);
        }

        .history-message:hover {
            background: rgba(255, 255, 255, 0.08);
            transform: translateX(4px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        [data-theme="light"] .history-message:hover {
            background: rgba(0, 0, 0, 0.04);
        }

        .history-message.system {
            border-left-color: var(--accent-green);
        }

        .history-message.user {
            border-left-color: var(--accent-orange);
        }

        .history-message-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 12px;
            color: var(--text-secondary);
        }

        .history-message-header span:first-child {
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.08);
        }

        .history-message.system .history-message-header span:first-child {
            background: rgba(78, 201, 176, 0.15);
            color: var(--accent-green);
        }

        .history-message.user .history-message-header span:first-child {
            background: rgba(255, 107, 53, 0.15);
            color: var(--accent-orange);
        }

        [data-theme="light"] .history-message-header span:first-child {
            background: rgba(0, 0, 0, 0.05);
        }

        [data-theme="light"] .history-message.system .history-message-header span:first-child {
            background: rgba(40, 167, 69, 0.15);
        }

        [data-theme="light"] .history-message.user .history-message-header span:first-child {
            background: rgba(253, 126, 20, 0.15);
        }

        .history-message-content {
            color: var(--text-primary);
            line-height: 1.7;
            font-size: 14px;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .history-date-group {
            margin-bottom: 24px;
        }

        .history-date-header {
            font-size: 15px;
            font-weight: 600;
            color: var(--accent-orange);
            margin-bottom: 16px;
            padding: 10px 14px;
            background: rgba(255, 107, 53, 0.1);
            border-radius: 12px;
            border: none;
        }

        .no-messages {
            text-align: center;
            color: var(--text-secondary);
            padding: 60px 20px;
            font-style: italic;
            font-size: 15px;
        }

        /* Notification animations */
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }

        /* Settings panel */
        .settings-panel {
            display: none;
            position: fixed;
            top: 60px;
            right: 20px;
            z-index: 1500;
            min-width: 300px;
        }

        .settings-content {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            box-shadow: 0 4px 20px var(--shadow-color);
            overflow: hidden;
        }

        .settings-header {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--bg-tertiary);
        }

        .settings-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--accent-orange);
        }

        .close-settings-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 14px;
            cursor: pointer;
            padding: 4px;
            border-radius: 4px;
            transition: all 0.2s ease;
        }

        .close-settings-btn:hover {
            background: var(--bg-primary);
            color: var(--text-primary);
        }

        .settings-body {
            padding: 16px;
        }

        .setting-item {
            margin-bottom: 16px;
        }

        .setting-item label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 8px;
        }

        .countdown-input {
            width: 100%;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.2s ease;
        }

        .countdown-input:focus {
            outline: none;
            border-color: var(--accent-orange);
        }

        .setting-description {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 4px;
            line-height: 1.4;
        }

        .setting-actions {
            margin-top: 20px;
            text-align: right;
        }

        .save-settings-btn {
            background: var(--accent-green);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .save-settings-btn:hover {
            background: #28a745;
            transform: translateY(-1px);
        }
    </style>
</head>
<body>
    <div class="connection-banner" id="connectionBanner">
        <i class="fas fa-exclamation-triangle"></i>
        <span id="connectionMessage">连接已断开，正在重新连接...</span>
    </div>
    
    <div class="drag-overlay" id="dragOverlay">
        <div class="drag-overlay-content">
            <i class="fas fa-cloud-upload-alt"></i>
            <p>拖放图片到这里上传</p>
        </div>
    </div>
    
    <div class="container">
        <div class="header">
            <div class="header-inner">
                <div class="status-indicator" id="statusIndicator"></div>
                <div class="header-title">Review Gate V2</div>
                <div class="status-text" id="statusText">正在连接...</div>
                <div class="countdown-container" id="countdownContainer">
                    <span class="countdown-label">自动发送</span>
                    <span class="countdown-time" id="countdownTime">--:--</span>
                </div>
                <div class="header-actions">
                    <button class="search-btn" id="searchBtn" title="搜索消息">
                        <i class="fas fa-search"></i> 搜索
                    </button>
                    <button class="history-btn" id="historyBtn" title="查看历史消息">
                        <i class="fas fa-history"></i> 历史
                    </button>
                    <button class="settings-btn" id="settingsBtn" title="设置">
                        <i class="fas fa-cog"></i>
                    </button>
                    <button class="theme-btn" id="themeBtn" title="切换主题">
                        <i class="fas fa-moon"></i>
                    </button>
                </div>
                <div class="author">by Lakshman Turlapati</div>
            </div>
        </div>
        
        <div class="messages-container" id="messagesContainer">
            <div class="messages-inner">
                <div class="welcome-message" id="welcomeMessage">
                    <h2>🎯 Review Gate V2 Web</h2>
                    <p>等待 Cursor Agent 发起审查请求...<br>
                    当 Agent 需要您的反馈时，消息将显示在这里。</p>
                </div>
            </div>
        </div>
        
        <div class="input-container" id="inputContainer">
            <div class="input-inner">
                <div class="input-wrapper">
                    <textarea 
                        id="messageInput" 
                        class="message-input" 
                        placeholder="等待 Agent 请求..." 
                        rows="1"
                        disabled
                    ></textarea>
                    <button class="attach-button" id="attachButton" title="上传图片" disabled>
                        <i class="fas fa-image"></i>
                    </button>
                </div>
                <button class="send-button" id="sendButton" title="发送" disabled>
                    <i class="fas fa-arrow-up"></i>
                </button>
            </div>
        </div>
    </div>
    
    <input type="file" id="fileInput" accept="image/*" multiple style="display: none;">

    <!-- Settings Panel -->
    <div class="settings-panel" id="settingsPanel">
        <div class="settings-content">
            <div class="settings-header">
                <div class="settings-title">设置</div>
                <button class="close-settings-btn" id="closeSettingsBtn" title="关闭">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="settings-body">
                <div class="setting-item">
                    <label for="countdownInput">自动发送倒计时 (秒)</label>
                    <input type="number" id="countdownInput" class="countdown-input"
                           min="30" max="600" step="30" value="300" placeholder="300">
                    <div class="setting-description">
                        设置 Agent 等待用户回复的超时时间 (30-600秒)
                    </div>
                </div>
                <div class="setting-item">
                    <label for="autoMessageInput">自动发送消息内容</label>
                    <input type="text" id="autoMessageInput" class="countdown-input"
                           value="继续" placeholder="继续">
                    <div class="setting-description">
                        倒计时结束后自动发送的消息内容
                    </div>
                </div>
                <div class="setting-actions">
                    <button class="save-settings-btn" id="saveSettingsBtn">保存设置</button>
                </div>
            </div>
        </div>
    </div>

    <!-- History Modal -->
    <div class="history-modal" id="historyModal">
        <div class="history-content">
            <div class="history-header">
                <div class="history-title">历史消息</div>
                <div class="history-controls">
                    <select class="date-selector" id="dateSelector">
                        <option value="recent">最近消息</option>
                    </select>
                    <button class="close-btn" id="closeHistoryBtn" title="关闭">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="history-body" id="historyBody">
                <div class="search-section">
                    <input type="text" class="search-input" id="historySearchInput" placeholder="搜索消息内容...">
                </div>
                <div id="historyMessages">
                    <div class="no-messages">暂无历史消息</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection
        let ws = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 10;
        let currentTriggerId = null;
        let attachedImages = [];
        let countdownTimer = null;

        // History related variables
        let availableDates = [];
        let currentHistoryMode = 'recent';

        // Theme related variables
        let currentTheme = 'dark';
        
        // DOM elements
        const messagesContainer = document.getElementById('messagesContainer');
        const messagesInner = messagesContainer.querySelector('.messages-inner');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const attachButton = document.getElementById('attachButton');
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const connectionBanner = document.getElementById('connectionBanner');
        const connectionMessage = document.getElementById('connectionMessage');
        const welcomeMessage = document.getElementById('welcomeMessage');
        const countdownContainer = document.getElementById('countdownContainer');
        const countdownTime = document.getElementById('countdownTime');
        const dragOverlay = document.getElementById('dragOverlay');
        const fileInput = document.getElementById('fileInput');
        const inputContainer = document.getElementById('inputContainer');

        // History elements
        const historyBtn = document.getElementById('historyBtn');
        const searchBtn = document.getElementById('searchBtn');
        const historyModal = document.getElementById('historyModal');
        const closeHistoryBtn = document.getElementById('closeHistoryBtn');
        const dateSelector = document.getElementById('dateSelector');
        const historySearchInput = document.getElementById('historySearchInput');
        const historyMessages = document.getElementById('historyMessages');

        // Theme elements
        const themeBtn = document.getElementById('themeBtn');
        const themeIcon = themeBtn.querySelector('i');

        // Settings elements
        const settingsBtn = document.getElementById('settingsBtn');
        const settingsPanel = document.getElementById('settingsPanel');
        const closeSettingsBtn = document.getElementById('closeSettingsBtn');
        const countdownInput = document.getElementById('countdownInput');
        const autoMessageInput = document.getElementById('autoMessageInput');
        const saveSettingsBtn = document.getElementById('saveSettingsBtn');

        // Auto message setting
        let autoMessage = localStorage.getItem('review-gate-auto-message') || '继续';
        
        // Connect to WebSocket
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            console.log('Connecting to WebSocket:', wsUrl);
            ws = new WebSocket(wsUrl);
            
            ws.onopen = async () => {
                console.log('WebSocket connected');
                reconnectAttempts = 0;
                updateConnectionStatus(true);
                connectionBanner.classList.remove('visible');
                
                // Load settings from server (local file)
                try {
                    const response = await fetch('/api/settings');
                    if (response.ok) {
                        const serverSettings = await response.json();
                        console.log('Loaded settings from server:', serverSettings);
                        
                        // Update local variables
                        autoMessage = serverSettings.auto_message || '继续';
                        
                        // Also update localStorage for consistency
                        localStorage.setItem('review-gate-timeout', serverSettings.timeout.toString());
                        localStorage.setItem('review-gate-auto-message', serverSettings.auto_message);
                        
                        // Send settings to WebSocket for this session
                        ws.send(JSON.stringify({
                            type: 'update_settings',
                            timeout: serverSettings.timeout,
                            auto_message: serverSettings.auto_message,
                            save_to_file: false  // Don't save again, just update session
                        }));
                    }
                } catch (e) {
                    console.log('Failed to load settings from server, using localStorage');
                    // Fallback to localStorage
                    const savedTimeout = parseInt(localStorage.getItem('review-gate-timeout') || '300');
                    const savedAutoMessage = localStorage.getItem('review-gate-auto-message') || '继续';
                    autoMessage = savedAutoMessage;
                    ws.send(JSON.stringify({
                        type: 'update_settings',
                        timeout: savedTimeout,
                        auto_message: savedAutoMessage,
                        save_to_file: false
                    }));
                }
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected');
                updateConnectionStatus(false);
                scheduleReconnect();
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                updateConnectionStatus(false);
            };
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleMessage(data);
                } catch (e) {
                    console.error('Error parsing message:', e);
                }
            };
        }
        
        function scheduleReconnect() {
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 30000);
                
                connectionBanner.classList.add('visible', 'reconnecting');
                connectionMessage.textContent = `连接已断开，${delay/1000}秒后重新连接... (${reconnectAttempts}/${maxReconnectAttempts})`;
                
                setTimeout(connect, delay);
            } else {
                connectionBanner.classList.add('visible');
                connectionBanner.classList.remove('reconnecting');
                connectionMessage.textContent = '无法连接到服务器，请刷新页面重试。';
            }
        }
        
        function updateConnectionStatus(connected) {
            if (connected) {
                statusIndicator.classList.add('connected');
                statusIndicator.classList.remove('disconnected');
                statusText.textContent = 'MCP 已连接';
            } else {
                statusIndicator.classList.remove('connected');
                statusIndicator.classList.add('disconnected');
                statusText.textContent = '已断开';
                disableInput();
            }
        }
        
        function handleMessage(data) {
            console.log('Received message:', data);
            
            switch (data.type) {
                case 'request':
                    handleReviewRequest(data);
                    break;
                case 'timeout':
                    handleTimeout(data);
                    break;
                case 'cancel':
                    handleCancel(data);
                    break;
                case 'status':
                    updateStatus(data);
                    break;
                case 'countdown':
                    updateCountdown(data.remaining, data.total);
                    break;
                case 'history_messages':
                    displayHistoryMessages(data.messages, data.request_type);
                    break;
                case 'history_dates':
                    updateDateSelector(data.dates);
                    break;
                case 'search_results':
                    displaySearchResults(data.messages, data.query);
                    break;
            }
        }
        
        function handleReviewRequest(data) {
            currentTriggerId = data.trigger_id;
            
            // Hide welcome message
            welcomeMessage.style.display = 'none';
            
            // Add system message
            addMessage(data.message, 'system', false);
            
            // Enable input
            enableInput();
            
            // Start countdown if configured
            if (data.timeout) {
                startCountdown(data.timeout);
            }
            
            // Focus input
            messageInput.focus();
            
            // Play notification sound (optional)
            playNotificationSound();
        }
        
        function handleTimeout(data) {
            addMessage('⏰ 请求已超时', 'system', true);
            disableInput();
            clearCountdown();
        }
        
        function handleCancel(data) {
            addMessage('❌ 请求已取消', 'system', true);
            disableInput();
            clearCountdown();
        }
        
        function updateStatus(data) {
            if (data.mcp_active !== undefined) {
                updateConnectionStatus(data.mcp_active);
            }
        }
        
        function enableInput() {
            messageInput.disabled = false;
            sendButton.disabled = false;
            attachButton.disabled = false;
            inputContainer.classList.remove('disabled');
            messageInput.placeholder = 'Cursor Agent 正在等待您的反馈...';
        }
        
        function disableInput() {
            messageInput.disabled = true;
            sendButton.disabled = true;
            attachButton.disabled = true;
            inputContainer.classList.add('disabled');
            messageInput.placeholder = '等待 Agent 请求...';
            currentTriggerId = null;
            clearCountdown();
        }
        
        function addMessage(text, type = 'user', plain = false) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${type}${plain ? ' plain' : ''}`;
            
            const bubbleDiv = document.createElement('div');
            bubbleDiv.className = 'message-bubble';
            bubbleDiv.textContent = text;
            
            messageDiv.appendChild(bubbleDiv);
            
            if (!plain) {
                const timeDiv = document.createElement('div');
                timeDiv.className = 'message-time';
                timeDiv.textContent = new Date().toLocaleTimeString('zh-CN');
                messageDiv.appendChild(timeDiv);
            }
            
            messagesInner.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        
        function sendMessage() {
            const text = messageInput.value.trim();
            if (!text && attachedImages.length === 0) return;
            if (!currentTriggerId) return;
            
            // Create display message
            let displayText = text;
            if (attachedImages.length > 0) {
                displayText += (text ? '\\n\\n' : '') + `[${attachedImages.length} 张图片已附加]`;
            }
            
            addMessage(displayText, 'user');
            
            // Send to server
            const message = {
                type: 'response',
                trigger_id: currentTriggerId,
                text: text,
                attachments: attachedImages,
                timestamp: new Date().toISOString()
            };
            
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(message));
            }
            
            // Clear input
            messageInput.value = '';
            attachedImages = [];
            adjustTextareaHeight();
            
            // Disable input until next request
            disableInput();
            
            // Show confirmation
            addMessage('✅ 反馈已发送给 Agent', 'system', true);
        }
        
        function adjustTextareaHeight() {
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        }
        
        function startCountdown(duration) {
            clearCountdown();
            
            let remaining = duration;
            countdownContainer.classList.add('active');
            
            const updateDisplay = () => {
                const minutes = Math.floor(remaining / 60);
                const seconds = remaining % 60;
                countdownTime.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
                
                if (remaining <= 30) {
                    countdownTime.classList.add('warning');
                } else {
                    countdownTime.classList.remove('warning');
                }
            };
            
            updateDisplay();
            
            countdownTimer = setInterval(() => {
                remaining--;
                if (remaining <= 0) {
                    clearCountdown();
                    // Auto submit with configured message
                    autoSubmitMessage();
                } else {
                    updateDisplay();
                }
            }, 1000);
        }

        function autoSubmitMessage() {
            if (currentTriggerId && !inputContainer.classList.contains('disabled')) {
                // Use the configured auto message
                const message = autoMessage || '继续';
                
                // Set the message in input and send
                messageInput.value = message;
                sendMessage();
            }
        }
        
        function clearCountdown() {
            if (countdownTimer) {
                clearInterval(countdownTimer);
                countdownTimer = null;
            }
            countdownContainer.classList.remove('active');
            countdownTime.classList.remove('warning');
        }
        
        function updateCountdown(remaining, total) {
            if (remaining <= 0) {
                clearCountdown();
                return;
            }
            
            countdownContainer.classList.add('active');
            const minutes = Math.floor(remaining / 60);
            const seconds = remaining % 60;
            countdownTime.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
            
            if (remaining <= 30) {
                countdownTime.classList.add('warning');
            } else {
                countdownTime.classList.remove('warning');
            }
        }
        
        function playNotificationSound() {
            // Create a simple notification sound
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();
                
                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);
                
                oscillator.frequency.value = 800;
                oscillator.type = 'sine';
                gainNode.gain.value = 0.1;
                
                oscillator.start();
                oscillator.stop(audioContext.currentTime + 0.1);
            } catch (e) {
                console.log('Could not play notification sound');
            }
        }
        
        // Image handling
        function handleImageUpload(files) {
            for (const file of files) {
                if (!file.type.startsWith('image/')) continue;
                
                const reader = new FileReader();
                reader.onload = (e) => {
                    const dataUrl = e.target.result;
                    const base64Data = dataUrl.split(',')[1];
                    
                    const imageData = {
                        id: 'img_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
                        fileName: file.name,
                        mimeType: file.type,
                        base64Data: base64Data,
                        dataUrl: dataUrl,
                        size: file.size
                    };
                    
                    attachedImages.push(imageData);
                    showImagePreview(imageData);
                };
                reader.readAsDataURL(file);
            }
        }
        
        function showImagePreview(imageData) {
            const previewDiv = document.createElement('div');
            previewDiv.className = 'message system image-preview';
            previewDiv.setAttribute('data-image-id', imageData.id);
            previewDiv.innerHTML = `
                <div class="message-bubble">
                    <div class="image-header">
                        <span class="image-filename">${imageData.fileName}</span>
                        <button class="remove-image-btn" onclick="removeImage('${imageData.id}')" title="移除图片">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <img src="${imageData.dataUrl}" alt="预览">
                    <div style="margin-top: 8px; font-size: 12px; opacity: 0.7;">
                        图片已准备发送 (${(imageData.size / 1024).toFixed(1)} KB)
                    </div>
                </div>
            `;
            messagesInner.appendChild(previewDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        
        function removeImage(imageId) {
            attachedImages = attachedImages.filter(img => img.id !== imageId);
            const preview = document.querySelector(`[data-image-id="${imageId}"]`);
            if (preview) preview.remove();
        }
        
        
        // Event listeners
        messageInput.addEventListener('input', adjustTextareaHeight);
        
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        sendButton.addEventListener('click', sendMessage);
        
        attachButton.addEventListener('click', () => {
            fileInput.click();
        });
        
        fileInput.addEventListener('change', (e) => {
            handleImageUpload(e.target.files);
            fileInput.value = '';
        });
        
        
        // Drag and drop
        let dragCounter = 0;
        
        document.addEventListener('dragenter', (e) => {
            e.preventDefault();
            dragCounter++;
            dragOverlay.classList.add('active');
        });
        
        document.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dragCounter--;
            if (dragCounter <= 0) {
                dragOverlay.classList.remove('active');
                dragCounter = 0;
            }
        });
        
        document.addEventListener('dragover', (e) => {
            e.preventDefault();
        });
        
        document.addEventListener('drop', (e) => {
            e.preventDefault();
            dragCounter = 0;
            dragOverlay.classList.remove('active');
            
            if (e.dataTransfer.files.length > 0) {
                handleImageUpload(e.dataTransfer.files);
            }
        });
        
        // Paste handling
        document.addEventListener('paste', (e) => {
            const items = e.clipboardData?.items;
            if (!items) return;
            
            for (const item of items) {
                if (item.type.startsWith('image/')) {
                    e.preventDefault();
                    const file = item.getAsFile();
                    if (file) handleImageUpload([file]);
                    break;
                }
            }
        });
        
        // History functions
        function showHistoryModal() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                // Request available dates
                ws.send(JSON.stringify({
                    type: 'get_history',
                    request_type: 'dates'
                }));

                // Show modal
                historyModal.classList.add('active');
                loadRecentHistory();
            }
        }

        function hideHistoryModal() {
            historyModal.classList.remove('active');
        }

        function loadRecentHistory() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'get_history',
                    request_type: 'recent'
                }));
            }
        }

        function loadHistoryByDate(date) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'get_history',
                    request_type: 'by_date',
                    date: date
                }));
            }
        }

        function searchMessages(query) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'search_messages',
                    query: query
                }));
            }
        }

        function updateDateSelector(dates) {
            availableDates = dates;
            dateSelector.innerHTML = '<option value="recent">最近消息</option>';

            dates.forEach(date => {
                const option = document.createElement('option');
                option.value = date;
                option.textContent = date;
                dateSelector.appendChild(option);
            });
        }

        function displayHistoryMessages(messages, requestType) {
            historyMessages.innerHTML = '';

            if (messages.length === 0) {
                historyMessages.innerHTML = '<div class="no-messages">暂无历史消息</div>';
                return;
            }

            // Group messages by date if not already grouped
            const groupedMessages = {};
            messages.forEach(msg => {
                const date = msg.date;
                if (!groupedMessages[date]) {
                    groupedMessages[date] = [];
                }
                groupedMessages[date].push(msg);
            });

            // Display grouped messages
            Object.keys(groupedMessages).sort().reverse().forEach(date => {
                const dateGroup = document.createElement('div');
                dateGroup.className = 'history-date-group';

                const dateHeader = document.createElement('div');
                dateHeader.className = 'history-date-header';
                dateHeader.textContent = date;
                dateGroup.appendChild(dateHeader);

                groupedMessages[date].forEach(msg => {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `history-message ${msg.type}`;

                    const headerDiv = document.createElement('div');
                    headerDiv.className = 'history-message-header';

                    const timestamp = new Date(msg.timestamp);
                    const timeStr = timestamp.toLocaleString('zh-CN');

                    headerDiv.innerHTML = `
                        <span>${msg.type === 'system' ? '系统消息' : '用户回复'}</span>
                        <span>${timeStr}</span>
                    `;

                    const contentDiv = document.createElement('div');
                    contentDiv.className = 'history-message-content';
                    contentDiv.textContent = msg.content;

                    messageDiv.appendChild(headerDiv);
                    messageDiv.appendChild(contentDiv);
                    dateGroup.appendChild(messageDiv);
                });

                historyMessages.appendChild(dateGroup);
            });
        }

        function displaySearchResults(messages, query) {
            historyMessages.innerHTML = '';

            if (messages.length === 0) {
                historyMessages.innerHTML = `<div class="no-messages">未找到包含"${query}"的消息</div>`;
                return;
            }

            const resultsHeader = document.createElement('div');
            resultsHeader.className = 'history-date-header';
            resultsHeader.textContent = `搜索结果："${query}" (${messages.length}条)`;
            historyMessages.appendChild(resultsHeader);

            messages.forEach(msg => {
                const messageDiv = document.createElement('div');
                messageDiv.className = `history-message ${msg.type}`;

                const headerDiv = document.createElement('div');
                headerDiv.className = 'history-message-header';

                const timestamp = new Date(msg.timestamp);
                const timeStr = timestamp.toLocaleString('zh-CN');

                headerDiv.innerHTML = `
                    <span>${msg.type === 'system' ? '系统消息' : '用户回复'}</span>
                    <span>${timeStr}</span>
                `;

                const contentDiv = document.createElement('div');
                contentDiv.className = 'history-message-content';
                contentDiv.textContent = msg.content;

                messageDiv.appendChild(headerDiv);
                messageDiv.appendChild(contentDiv);
                historyMessages.appendChild(messageDiv);
            });
        }

        // History event listeners
        historyBtn.addEventListener('click', showHistoryModal);
        searchBtn.addEventListener('click', () => {
            showHistoryModal();
            // Focus on search input after modal opens
            setTimeout(() => {
                historySearchInput.focus();
            }, 100);
        });
        closeHistoryBtn.addEventListener('click', hideHistoryModal);

        dateSelector.addEventListener('change', (e) => {
            const selectedValue = e.target.value;
            currentHistoryMode = selectedValue;

            if (selectedValue === 'recent') {
                loadRecentHistory();
            } else {
                loadHistoryByDate(selectedValue);
            }
        });

        historySearchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            if (query.length > 0) {
                searchMessages(query);
            } else {
                // Reload current view
                if (currentHistoryMode === 'recent') {
                    loadRecentHistory();
                } else {
                    loadHistoryByDate(currentHistoryMode);
                }
            }
        });

        // Close modal when clicking outside
        historyModal.addEventListener('click', (e) => {
            if (e.target === historyModal) {
                hideHistoryModal();
            }
        });

        // Theme functions
        function initTheme() {
            // Load saved theme preference
            const savedTheme = localStorage.getItem('review-gate-theme') || 'dark';
            setTheme(savedTheme);
        }

        function setTheme(theme) {
            currentTheme = theme;
            document.documentElement.setAttribute('data-theme', theme);

            // Update button icon
            if (theme === 'dark') {
                themeIcon.className = 'fas fa-moon';
                themeBtn.title = '切换到浅色主题';
            } else {
                themeIcon.className = 'fas fa-sun';
                themeBtn.title = '切换到深色主题';
            }

            // Save preference
            localStorage.setItem('review-gate-theme', theme);
        }

        function toggleTheme() {
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
        }

        // Theme event listeners
        themeBtn.addEventListener('click', toggleTheme);

        // Settings functions
        function showSettingsPanel() {
            // Load current settings
            const savedTimeout = localStorage.getItem('review-gate-timeout') || '300';
            const savedAutoMessage = localStorage.getItem('review-gate-auto-message') || '继续';
            countdownInput.value = savedTimeout;
            autoMessageInput.value = savedAutoMessage;

            settingsPanel.style.display = 'block';
            countdownInput.focus();
        }

        function hideSettingsPanel() {
            settingsPanel.style.display = 'none';
        }

        function saveSettings() {
            const newTimeout = parseInt(countdownInput.value);
            const newAutoMessage = autoMessageInput.value.trim() || '继续';

            // Validate timeout (30-600 seconds)
            if (newTimeout < 30 || newTimeout > 600) {
                alert('倒计时时间必须在 30-600 秒之间');
                countdownInput.focus();
                return;
            }

            // Save to localStorage
            localStorage.setItem('review-gate-timeout', newTimeout.toString());
            localStorage.setItem('review-gate-auto-message', newAutoMessage);
            autoMessage = newAutoMessage;

            // Send to server if WebSocket is connected
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'update_settings',
                    timeout: newTimeout,
                    auto_message: newAutoMessage
                }));
            }

            // Close panel
            hideSettingsPanel();

            // Show confirmation
            showNotification(`设置已保存：倒计时 ${newTimeout} 秒，自动消息 "${newAutoMessage}"`);
        }

        function showNotification(message) {
            // Simple notification - you could enhance this
            const notification = document.createElement('div');
            notification.textContent = message;
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: var(--accent-green);
                color: white;
                padding: 12px 16px;
                border-radius: 6px;
                font-size: 14px;
                z-index: 2000;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                animation: slideInRight 0.3s ease;
            `;

            document.body.appendChild(notification);

            setTimeout(() => {
                notification.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }, 3000);
        }

        // Settings event listeners
        settingsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (settingsPanel.style.display === 'block') {
                hideSettingsPanel();
            } else {
                showSettingsPanel();
            }
        });
        closeSettingsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            hideSettingsPanel();
        });
        saveSettingsBtn.addEventListener('click', saveSettings);

        // Settings panel should only close via close button or save button
        // Remove the outside click close behavior per user request

        // Handle Enter key in countdown input
        countdownInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                saveSettings();
            }
        });

        // Initialize theme on page load
        initTheme();

        // Initialize
        connect();
    </script>
</body>
</html>'''

    async def handle_index(self, request: web.Request) -> web.Response:
        """Serve the main HTML page"""
        return web.Response(
            text=self.get_html_content(),
            content_type='text/html',
            charset='utf-8'
        )

    async def handle_get_settings(self, request: web.Request) -> web.Response:
        """Return saved settings from local file"""
        settings = load_user_settings()
        return web.json_response(settings)
    
    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.websockets.add(ws)
        logger.info(safe_log(f"WebSocket client connected. Total clients: {len(self.websockets)}"))
        
        # Send current status
        await ws.send_json({
            'type': 'status',
            'mcp_active': True,
            'message': 'Connected to Review Gate V2 Web Server'
        })
        
        # If there's a pending request, send it
        if self.current_request:
            # Load user settings from local file to get the configured timeout
            user_settings = load_user_settings()
            client_timeout = user_settings.get('timeout', 300)
            
            # Also set on the ws object for future use
            ws.user_timeout = client_timeout
            ws.user_auto_message = user_settings.get('auto_message', '继续')
            
            await ws.send_json({
                'type': 'request',
                'trigger_id': self.current_request.trigger_id,
                'message': self.current_request.message,
                'title': self.current_request.title,
                'context': self.current_request.context,
                'urgent': self.current_request.urgent,
                'timeout': client_timeout
            })
            logger.info(safe_log(f"Sent pending request with timeout={client_timeout}s from local settings"))
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.handle_ws_message(ws, data)
                    except json.JSONDecodeError:
                        logger.error(safe_log(f"Invalid JSON from WebSocket: {msg.data}"))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(safe_log(f"WebSocket error: {ws.exception()}"))
        finally:
            self.websockets.discard(ws)
            logger.info(safe_log(f"WebSocket client disconnected. Total clients: {len(self.websockets)}"))
        
        return ws
    
    async def handle_ws_message(self, ws: web.WebSocketResponse, data: Dict[str, Any]):
        """Handle incoming WebSocket messages"""
        msg_type = data.get('type')

        if msg_type == 'response':
            trigger_id = data.get('trigger_id')
            text = data.get('text', '')
            attachments = data.get('attachments', [])

            # Safe logging for Chinese characters
            log_text = text[:100] if text else ''
            logger.info(safe_log(f"Received response for trigger {trigger_id}: {log_text}..."))

            # Save user message to history
            if text:
                user_message = MessageRecord(
                    id=f"msg_{int(time.time() * 1000)}_{trigger_id}",
                    trigger_id=trigger_id,
                    message_type='user',
                    content=text,
                    timestamp=datetime.now().isoformat(),
                    date=datetime.now().strftime('%Y-%m-%d'),
                    has_attachments=len(attachments) > 0,
                    attachments=attachments
                )
                self.message_storage.save_message(user_message)

            # Find and resolve the pending request
            if self.current_request and self.current_request.trigger_id == trigger_id:
                if not self.current_request.future.done():
                    self.current_request.future.set_result({
                        'text': text,
                        'attachments': attachments
                    })
                self.current_request = None

        elif msg_type == 'get_history':
            # Handle history requests
            await self._handle_history_request(ws, data)

        elif msg_type == 'search_messages':
            # Handle search requests
            await self._handle_search_request(ws, data)

        elif msg_type == 'update_settings':
            # Handle settings updates
            await self._handle_settings_update(ws, data)
                
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected WebSocket clients"""
        if not self.websockets:
            return
            
        disconnected = set()
        for ws in self.websockets:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(safe_log(f"Error broadcasting to WebSocket: {e}"))
                disconnected.add(ws)
        
        self.websockets -= disconnected

    async def _broadcast_with_client_timeouts(self, message: Dict[str, Any], default_timeout: int = 300):
        """Broadcast a message to all connected clients with their configured timeouts"""
        if not self.websockets:
            return

        disconnected = set()
        for ws in self.websockets:
            try:
                # Use client-configured timeout if available, otherwise use default
                client_timeout = getattr(ws, 'user_timeout', default_timeout)
                client_message = {**message, 'timeout': client_timeout}
                await ws.send_json(client_message)
            except Exception as e:
                logger.error(safe_log(f"Error broadcasting to WebSocket: {e}"))
                disconnected.add(ws)

        self.websockets -= disconnected
    
    async def send_review_request(
        self,
        trigger_id: str,
        message: str,
        title: str = "Review Gate V2",
        context: str = "",
        urgent: bool = False,
        timeout: Optional[int] = None  # Kept for backward compatibility, but not used
    ) -> Optional[Dict[str, Any]]:
        """
        Send a review request to the web interface and wait for response.
        
        MCP service waits indefinitely for user response.
        The timeout parameter is only used for the countdown display in the web UI.
        """
        # Create pending request
        loop = asyncio.get_event_loop()
        request = PendingRequest(
            trigger_id=trigger_id,
            message=message,
            title=title,
            context=context,
            urgent=urgent,
            timestamp=datetime.now().isoformat(),
            tool="review_gate_chat",
            future=loop.create_future()
        )
        
        self.current_request = request
        self.pending_requests[trigger_id] = request
        
        # Save system message to history
        system_message = MessageRecord(
            id=f"msg_{int(time.time() * 1000)}_{trigger_id}_system",
            trigger_id=trigger_id,
            message_type='system',
            content=message,
            timestamp=datetime.now().isoformat(),
            date=datetime.now().strftime('%Y-%m-%d'),
            has_attachments=False,
            attachments=[]
        )
        self.message_storage.save_message(system_message)

        # Broadcast to all connected clients with their configured timeout
        await self._broadcast_with_client_timeouts({
            'type': 'request',
            'trigger_id': trigger_id,
            'message': message,
            'title': title,
            'context': context,
            'urgent': urgent
        }, timeout)
        
        logger.info(safe_log(f"Sent review request to {len(self.websockets)} web clients"))
        
        # Start countdown broadcast
        countdown_task = asyncio.create_task(
            self._broadcast_countdown(trigger_id, timeout)
        )
        
        try:
            # Wait for response indefinitely (no timeout)
            # The countdown in the web UI is just for display, MCP service waits forever
            result = await request.future
            countdown_task.cancel()
            return result
        except asyncio.CancelledError:
            countdown_task.cancel()
            return None
        finally:
            self.pending_requests.pop(trigger_id, None)
            if self.current_request and self.current_request.trigger_id == trigger_id:
                self.current_request = None

    async def _handle_history_request(self, ws: web.WebSocketResponse, data: Dict[str, Any]):
        """Handle history message requests"""
        request_type = data.get('request_type', 'recent')

        try:
            if request_type == 'by_date':
                target_date = data.get('date')
                if target_date:
                    messages = self.message_storage.get_messages_by_date(target_date)
                else:
                    messages = []
            elif request_type == 'dates':
                # Return available dates
                dates = self.message_storage.get_available_dates()
                await ws.send_json({
                    'type': 'history_dates',
                    'dates': dates
                })
                return
            else:  # recent
                messages = self.message_storage.get_recent_messages()

            # Convert messages to dict format
            message_list = []
            for msg in messages:
                message_list.append({
                    'id': msg.id,
                    'trigger_id': msg.trigger_id,
                    'type': msg.message_type,
                    'content': msg.content,
                    'timestamp': msg.timestamp,
                    'date': msg.date,
                    'has_attachments': msg.has_attachments,
                    'attachments': msg.attachments
                })

            await ws.send_json({
                'type': 'history_messages',
                'request_type': request_type,
                'messages': message_list
            })

        except Exception as e:
            logger.error(safe_log(f"Failed to handle history request: {e}"))
            await ws.send_json({
                'type': 'error',
                'message': 'Failed to retrieve history'
            })

    async def _handle_search_request(self, ws: web.WebSocketResponse, data: Dict[str, Any]):
        """Handle message search requests"""
        query = data.get('query', '').strip()

        if not query:
            await ws.send_json({
                'type': 'search_results',
                'query': query,
                'messages': []
            })
            return

        try:
            messages = self.message_storage.search_messages(query)

            # Convert messages to dict format
            message_list = []
            for msg in messages:
                message_list.append({
                    'id': msg.id,
                    'trigger_id': msg.trigger_id,
                    'type': msg.message_type,
                    'content': msg.content,
                    'timestamp': msg.timestamp,
                    'date': msg.date,
                    'has_attachments': msg.has_attachments,
                    'attachments': msg.attachments
                })

            await ws.send_json({
                'type': 'search_results',
                'query': query,
                'messages': message_list
            })

        except Exception as e:
            logger.error(safe_log(f"Failed to handle search request: {e}"))
            await ws.send_json({
                'type': 'error',
                'message': 'Failed to search messages'
            })

    async def _handle_settings_update(self, ws: web.WebSocketResponse, data: Dict[str, Any]):
        """Handle settings updates from client"""
        try:
            timeout = data.get('timeout', 300)
            auto_message = data.get('auto_message', '继续')
            save_to_file = data.get('save_to_file', True)

            # Validate timeout range
            if timeout < 30 or timeout > 600:
                await ws.send_json({
                    'type': 'settings_error',
                    'message': 'Timeout must be between 30 and 600 seconds'
                })
                return

            # Store the user-configured settings for this WebSocket client
            # This will be used for future review requests from this client
            ws.user_timeout = timeout
            ws.user_auto_message = auto_message

            # Save to local file if requested
            if save_to_file:
                current_settings = load_user_settings()
                current_settings['timeout'] = timeout
                current_settings['auto_message'] = auto_message
                save_user_settings(current_settings)
                logger.info(safe_log(f"Settings saved to local file"))

            await ws.send_json({
                'type': 'settings_updated',
                'timeout': timeout,
                'auto_message': auto_message,
                'message': f'Settings updated: timeout={timeout}s, auto_message="{auto_message}"'
            })

            logger.info(safe_log(f"Updated settings: timeout={timeout}s, auto_message='{auto_message}' for WebSocket client"))

        except Exception as e:
            logger.error(safe_log(f"Failed to handle settings update: {e}"))
            await ws.send_json({
                'type': 'settings_error',
                'message': 'Failed to update settings'
            })
    
    async def _broadcast_countdown(self, trigger_id: str, total: int):
        """Broadcast countdown updates"""
        remaining = total
        while remaining > 0:
            await asyncio.sleep(1)
            remaining -= 1
            
            # Only broadcast every 10 seconds or when < 30 seconds
            if remaining <= 30 or remaining % 10 == 0:
                await self.broadcast({
                    'type': 'countdown',
                    'trigger_id': trigger_id,
                    'remaining': remaining,
                    'total': total
                })
    
    async def start(self):
        """Start the web server"""
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp not available. Cannot start web server.")
            return False
        
        try:
            self.app = web.Application()
            self.app.router.add_get('/', self.handle_index)
            self.app.router.add_get('/ws', self.handle_websocket)
            self.app.router.add_get('/api/settings', self.handle_get_settings)
            
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(
                self.runner,
                self.config.host,
                self.config.port
            )
            await self.site.start()
            
            self._running = True
            
            url = f"http://{self.config.host}:{self.config.port}"
            logger.info(safe_log(f"Review Gate Web Server started at {url}"))
            
            # Auto-open browser
            if self.config.auto_open_browser:
                threading.Thread(
                    target=lambda: webbrowser.open(url),
                    daemon=True
                ).start()
                logger.info(safe_log(f"Opening browser at {url}"))
            
            return True
            
        except Exception as e:
            logger.error(safe_log(f"Failed to start web server: {e}"))
            return False
    
    async def stop(self):
        """Stop the web server"""
        self._running = False
        
        # Close all WebSocket connections
        for ws in list(self.websockets):
            await ws.close()
        self.websockets.clear()
        
        # Cancel pending requests
        for request in self.pending_requests.values():
            if not request.future.done():
                request.future.cancel()
        self.pending_requests.clear()
        
        # Stop the server
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("Review Gate Web Server stopped")
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def client_count(self) -> int:
        return len(self.websockets)


# Singleton instance for integration with MCP server
_web_server_instance: Optional[ReviewGateWebServer] = None


def get_web_server(config: Optional[WebServerConfig] = None) -> ReviewGateWebServer:
    """Get or create the web server singleton"""
    global _web_server_instance
    if _web_server_instance is None:
        _web_server_instance = ReviewGateWebServer(config)
    return _web_server_instance


async def start_web_server(config: Optional[WebServerConfig] = None) -> ReviewGateWebServer:
    """Start the web server and return the instance"""
    server = get_web_server(config)
    if not server.is_running:
        await server.start()
    return server


async def stop_web_server():
    """Stop the web server"""
    global _web_server_instance
    if _web_server_instance and _web_server_instance.is_running:
        await _web_server_instance.stop()

