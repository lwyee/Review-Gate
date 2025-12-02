#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Review Gate V2 - 配置管理模块

集中管理所有配置项，供 review_gate_web.py 和 web_server.py 使用。

配置优先级（从高到低）：
1. 命令行参数 (通过 MCP args 传入)
2. 用户配置文件 (settings.json)
3. 默认配置 (DEFAULT_SETTINGS)
"""

import json
import os
import sys
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ============================================================================
# Web Server Configuration - Web 服务器配置
# ============================================================================

DEFAULT_WEB_PORT = 8865                    # Web 服务器默认端口
DEFAULT_HOST = "127.0.0.1"                 # Web 服务器默认主机地址
AUTO_OPEN_BROWSER = True                   # 是否自动打开浏览器

# ============================================================================
# Default User Settings - 默认用户设置 (会被用户配置文件覆盖)
# ============================================================================

DEFAULT_SETTINGS = {
    'timeout': 300,                        # 倒计时超时时间（秒），范围 30-600
    'auto_message': '继续',                 # 超时后自动发送的消息
    'theme': 'dark',                       # 界面主题: 'dark' 或 'light'
    'use_web_interface': True,             # True: 优先使用 Web 接口, False: 强制使用 VSCode 插件
}

# ============================================================================
# Helper Functions - 辅助函数
# ============================================================================


def safe_log(message: str) -> str:
    """Safely encode message for logging on Windows"""
    if sys.platform == 'win32':
        try:
            return message.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        except Exception:
            return message.encode('ascii', errors='replace').decode('ascii', errors='replace')
    return message


def get_settings_dir() -> str:
    """Get the settings directory path based on OS"""
    if os.name == 'nt':  # Windows
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(app_data, 'ReviewGateV2')
    else:  # macOS and Linux
        return os.path.expanduser('~/.config/review-gate-v2')


def get_settings_file_path() -> str:
    """Get the path to the user settings file"""
    settings_dir = get_settings_dir()
    os.makedirs(settings_dir, exist_ok=True)
    return os.path.join(settings_dir, 'settings.json')


def load_user_settings() -> Dict[str, Any]:
    """
    Load user settings from local file.
    Returns settings merged with defaults.
    """
    settings_file = get_settings_file_path()
    # 使用默认配置的副本
    settings = DEFAULT_SETTINGS.copy()
    
    try:
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
                # Merge with defaults
                settings.update(saved_settings)
    except Exception as e:
        logger.warning(safe_log(f"Failed to load settings: {e}"))
    
    return settings


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


def get_effective_settings(cli_args=None) -> Dict[str, Any]:
    """
    Get settings with command line overrides applied.
    
    Args:
        cli_args: Parsed command line arguments (argparse Namespace)
    
    Returns:
        Effective settings dict with CLI overrides applied
    """
    settings = load_user_settings()
    
    # Apply command line overrides
    if cli_args:
        if hasattr(cli_args, 'use_web_interface') and cli_args.use_web_interface is not None:
            settings['use_web_interface'] = cli_args.use_web_interface.lower() == 'true'
        if hasattr(cli_args, 'timeout') and cli_args.timeout is not None:
            settings['timeout'] = cli_args.timeout
        if hasattr(cli_args, 'auto_message') and cli_args.auto_message is not None:
            settings['auto_message'] = cli_args.auto_message
    
    return settings


# ============================================================================
# Web Server Config Dataclass - Web 服务器配置数据类
# ============================================================================

@dataclass
class WebServerConfig:
    """Configuration for the web server"""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_WEB_PORT
    auto_open_browser: bool = AUTO_OPEN_BROWSER
    timeout_duration: int = DEFAULT_SETTINGS['timeout']
    show_countdown: bool = True


def create_web_config(cli_args=None) -> WebServerConfig:
    """
    Create WebServerConfig from command line arguments.
    
    Args:
        cli_args: Parsed command line arguments
    
    Returns:
        WebServerConfig instance
    """
    host = DEFAULT_HOST
    port = DEFAULT_WEB_PORT
    auto_open_browser = AUTO_OPEN_BROWSER
    
    if cli_args:
        if hasattr(cli_args, 'host') and cli_args.host:
            host = cli_args.host
        if hasattr(cli_args, 'port') and cli_args.port:
            port = cli_args.port
        if hasattr(cli_args, 'no_browser') and cli_args.no_browser:
            auto_open_browser = False
    
    return WebServerConfig(
        host=host,
        port=port,
        auto_open_browser=auto_open_browser
    )

