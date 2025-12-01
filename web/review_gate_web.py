#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Review Gate 2.0 - Advanced MCP Server with Web Interface
Author: Lakshman Turlapati (Original), Extended for Web Support

This version includes an integrated web server that automatically starts
when the MCP server starts, eliminating the need for a VSCode extension.

Features:
- MCP server for Cursor Agent integration
- Built-in web interface with WebSocket support
- Real-time communication without file polling
- Image upload support
- Auto-launch browser on startup
- Windows Chinese encoding support

Requirements:
- mcp>=1.9.2
- aiohttp>=3.9.0
- Python 3.8+
"""

import asyncio
import json
import sys
import logging
import os
import time
import glob
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

# Fix Windows console encoding for Chinese characters
if sys.platform == 'win32':
    try:
        # Set stdout/stderr to UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        # Set environment variable for subprocess
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    except Exception:
        pass

# Speech-to-text functionality removed

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
    ImageContent,
)

# Import web server
try:
    from web_server import (
        ReviewGateWebServer,
        WebServerConfig,
        get_web_server,
        load_user_settings,
        start_web_server,
        stop_web_server,
        AIOHTTP_AVAILABLE,
        safe_log
    )
    WEB_SERVER_AVAILABLE = True
except ImportError as e:
    WEB_SERVER_AVAILABLE = False
    AIOHTTP_AVAILABLE = False
    print(f"Warning: Web server module not available: {e}", file=sys.stderr)
    
    def safe_log(msg):
        """Fallback safe_log function"""
        if sys.platform == 'win32':
            try:
                return msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            except Exception:
                return msg.encode('ascii', errors='replace').decode('ascii', errors='replace')
        return msg

    def load_user_settings():
        """Fallback load_user_settings function"""
        import json
        default_settings = {
            'timeout': 300,
            'auto_message': '继续',
            'theme': 'dark'
        }
        try:
            if os.name == 'nt':
                app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
                settings_dir = os.path.join(app_data, 'ReviewGateV2')
            else:
                settings_dir = os.path.expanduser('~/.config/review-gate-v2')
            
            settings_file = os.path.join(settings_dir, 'settings.json')
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    default_settings.update(saved_settings)
        except Exception:
            pass
        return default_settings


# Cross-platform temp directory helper
def get_temp_path(filename: str) -> str:
    """Get cross-platform temporary file path"""
    if os.name == 'nt':  # Windows
        temp_dir = tempfile.gettempdir()
    else:  # macOS and Linux
        temp_dir = '/tmp'
    return os.path.join(temp_dir, filename)


# Configure logging with UTF-8 encoding
log_file_path = get_temp_path('review_gate_v2_web.log')

handlers = []
try:
    file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    handlers.append(file_handler)
except Exception as e:
    print(f"Warning: Could not create log file: {e}", file=sys.stderr)

# Custom stream handler with UTF-8 encoding for Windows
class SafeStreamHandler(logging.StreamHandler):
    """Stream handler that safely handles Unicode on Windows"""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Safely encode for Windows console
            if sys.platform == 'win32':
                try:
                    stream.write(msg + self.terminator)
                except UnicodeEncodeError:
                    # Fallback: replace problematic characters
                    safe_msg = msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                    stream.write(safe_msg + self.terminator)
            else:
                stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

stderr_handler = SafeStreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO)
handlers.append(stderr_handler)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)


class ReviewGateServerWeb:
    """Review Gate MCP Server with integrated Web Interface"""
    
    def __init__(self, web_config: Optional[WebServerConfig] = None):
        self.server = Server("review-gate-v2")
        self.setup_handlers()
        self.shutdown_requested = False
        self.shutdown_reason = ""
        self._last_attachments = []

        # Web server configuration
        self.web_config = web_config or WebServerConfig(
            host="127.0.0.1",
            port=8765,
            auto_open_browser=True,
            timeout_duration=300
        )
        self.web_server: Optional[ReviewGateWebServer] = None
        
        logger.info(safe_log("Review Gate 2.0 Web Server initialized"))
        logger.info(safe_log(f"Web interface will be available at http://{self.web_config.host}:{self.web_config.port}"))


    def setup_handlers(self):
        """Set up MCP request handlers"""
        
        @self.server.list_tools()
        async def list_tools():
            """List available Review Gate tools"""
            logger.info(safe_log("Cursor Agent requesting available tools"))
            tools = [
                Tool(
                    name="review_gate_chat",
                    description="Open Review Gate chat popup for feedback and reviews. Use this when you need user input. The popup will appear in the web browser and wait for user response for up to 5 minutes.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "The message to display in the Review Gate popup",
                                "default": "Please provide your review or feedback:"
                            },
                            "title": {
                                "type": "string", 
                                "description": "Title for the Review Gate popup window",
                                "default": "Review Gate V2"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context about what needs review",
                                "default": ""
                            },
                            "urgent": {
                                "type": "boolean",
                                "description": "Whether this is an urgent review request",
                                "default": False
                            }
                        }
                    }
                )
            ]
            logger.info(safe_log(f"Listed {len(tools)} Review Gate tools"))
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """Handle tool calls from Cursor Agent"""
            logger.info(safe_log(f"CURSOR AGENT CALLED TOOL: {name}"))
            logger.info(safe_log(f"Tool arguments: {arguments}"))
            
            await asyncio.sleep(0.5)
            
            try:
                if name == "review_gate_chat":
                    return await self._handle_review_gate_chat(arguments)
                else:
                    logger.error(safe_log(f"Unknown tool: {name}"))
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(safe_log(f"Tool call error for {name}: {e}"))
                return [TextContent(type="text", text=f"ERROR: Tool {name} failed: {str(e)}")]

    async def _handle_review_gate_chat(self, args: dict) -> list[TextContent]:
        """Handle Review Gate chat - routes to web interface or file-based fallback"""
        message = args.get("message", "Please provide your review or feedback:")
        title = args.get("title", "Review Gate V2")
        context = args.get("context", "")
        urgent = args.get("urgent", False)
        
        trigger_id = f"review_{int(time.time() * 1000)}"
        
        logger.info(safe_log(f"Review Gate chat request: {message[:100]}..."))
        
        # Try web interface first
        if self.web_server and self.web_server.is_running and self.web_server.client_count > 0:
            logger.info(safe_log(f"Using web interface ({self.web_server.client_count} clients connected)"))
            
            # Load user-configured timeout for countdown display only
            user_settings = load_user_settings()
            countdown_duration = user_settings.get('timeout', 300)
            logger.info(safe_log(f"Countdown display duration: {countdown_duration} seconds (MCP waits indefinitely)"))
            
            result = await self.web_server.send_review_request(
                trigger_id=trigger_id,
                message=message,
                title=title,
                context=context,
                urgent=urgent,
                timeout=countdown_duration  # Only for countdown display, MCP waits forever
            )
            
            if result:
                user_input = result.get('text', '')
                attachments = result.get('attachments', [])
                
                logger.info(safe_log(f"Received response from web interface: {user_input[:100]}..."))
                
                response_content = [TextContent(type="text", text=f"User Response: {user_input}")]
                
                # Handle image attachments
                if attachments:
                    self._last_attachments = attachments
                    for attachment in attachments:
                        if attachment.get('mimeType', '').startswith('image/'):
                            try:
                                image_content = ImageContent(
                                    type="image",
                                    data=attachment['base64Data'],
                                    mimeType=attachment['mimeType']
                                )
                                response_content.append(image_content)
                                logger.info(safe_log(f"Added image: {attachment.get('fileName', 'unknown')}"))
                            except Exception as e:
                                logger.error(safe_log(f"Error adding image: {e}"))
                
                return response_content
            else:
                logger.warning(safe_log("Web interface timed out"))
                return [TextContent(type="text", text="TIMEOUT: No user input received within 5 minutes")]
        
        # Fallback to file-based communication (for VSCode extension compatibility)
        logger.info(safe_log("Using file-based communication (no web clients connected)"))
        return await self._handle_review_gate_chat_file(args, trigger_id)

    async def _handle_review_gate_chat_file(self, args: dict, trigger_id: str) -> list[TextContent]:
        """File-based fallback for VSCode extension compatibility"""
        message = args.get("message", "Please provide your review or feedback:")
        title = args.get("title", "Review Gate V2")
        context = args.get("context", "")
        urgent = args.get("urgent", False)
        
        # Create trigger file for Cursor extension
        success = await self._trigger_cursor_popup_immediately({
            "tool": "review_gate_chat",
            "message": message,
            "title": title,
            "context": context,
            "urgent": urgent,
            "trigger_id": trigger_id,
            "timestamp": datetime.now().isoformat(),
            "immediate_activation": True
        })
        
        if success:
            logger.info(safe_log("Trigger file created - waiting for user input"))
            
            # Wait for acknowledgement
            ack_received = await self._wait_for_extension_acknowledgement(trigger_id, timeout=30)
            if ack_received:
                logger.info(safe_log("Extension acknowledged"))
            else:
                logger.warning(safe_log("No extension acknowledgement - popup may not have opened"))
            
            # Wait for user input indefinitely (no timeout)
            user_input = await self._wait_for_user_input(trigger_id)
            
            if user_input:
                logger.info(safe_log(f"Received user input: {user_input[:100]}..."))
                
                response_content = [TextContent(type="text", text=f"User Response: {user_input}")]
                
                if hasattr(self, '_last_attachments') and self._last_attachments:
                    for attachment in self._last_attachments:
                        if attachment.get('mimeType', '').startswith('image/'):
                            try:
                                image_content = ImageContent(
                                    type="image",
                                    data=attachment['base64Data'],
                                    mimeType=attachment['mimeType']
                                )
                                response_content.append(image_content)
                            except Exception as e:
                                logger.error(safe_log(f"Error adding image: {e}"))
                
                return response_content
            else:
                return [TextContent(type="text", text="TIMEOUT: No user input received within 5 minutes")]
        else:
            return [TextContent(type="text", text="ERROR: Failed to trigger Review Gate popup")]

    async def _wait_for_extension_acknowledgement(self, trigger_id: str, timeout: int = 30) -> bool:
        """Wait for extension acknowledgement"""
        ack_file = Path(get_temp_path(f"review_gate_ack_{trigger_id}.json"))
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if ack_file.exists():
                    data = json.loads(ack_file.read_text(encoding='utf-8'))
                    ack_status = data.get("acknowledged", False)
                    try:
                        ack_file.unlink()
                    except:
                        pass
                    if ack_status:
                        return True
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(safe_log(f"Error reading ack file: {e}"))
                await asyncio.sleep(0.5)
        
        return False

    async def _wait_for_user_input(self, trigger_id: str) -> Optional[str]:
        """Wait for user input from file indefinitely"""
        response_patterns = [
            Path(get_temp_path(f"review_gate_response_{trigger_id}.json")),
            Path(get_temp_path("review_gate_response.json")),
            Path(get_temp_path(f"mcp_response_{trigger_id}.json")),
            Path(get_temp_path("mcp_response.json"))
        ]
        
        # Wait indefinitely for user input
        while True:
            try:
                for response_file in response_patterns:
                    if response_file.exists():
                        try:
                            file_content = response_file.read_text(encoding='utf-8').strip()
                            
                            if file_content.startswith('{'):
                                data = json.loads(file_content)
                                user_input = data.get("user_input", data.get("response", data.get("message", ""))).strip()
                                attachments = data.get("attachments", [])
                                
                                response_trigger_id = data.get("trigger_id", "")
                                if response_trigger_id and response_trigger_id != trigger_id:
                                    continue
                                
                                if attachments:
                                    self._last_attachments = attachments
                                else:
                                    self._last_attachments = []
                            else:
                                user_input = file_content
                                self._last_attachments = []
                            
                            try:
                                response_file.unlink()
                            except:
                                pass
                            
                            if user_input:
                                return user_input
                                
                        except json.JSONDecodeError as e:
                            logger.error(safe_log(f"JSON decode error: {e}"))
                        except Exception as e:
                            logger.error(safe_log(f"Error processing response file: {e}"))
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(safe_log(f"Error in wait loop: {e}"))
                await asyncio.sleep(0.5)
        
        return None

    async def _trigger_cursor_popup_immediately(self, data: dict) -> bool:
        """Create trigger file for Cursor extension"""
        try:
            await asyncio.sleep(0.1)
            
            trigger_file = Path(get_temp_path("review_gate_trigger.json"))
            
            trigger_data = {
                "timestamp": datetime.now().isoformat(),
                "system": "review-gate-v2",
                "editor": "cursor",
                "data": data,
                "pid": os.getpid(),
                "active_window": True,
                "mcp_integration": True,
                "immediate_activation": True
            }
            
            trigger_file.write_text(json.dumps(trigger_data, indent=2, ensure_ascii=False), encoding='utf-8')
            
            # Create backup triggers
            for i in range(3):
                backup_trigger = Path(get_temp_path(f"review_gate_trigger_{i}.json"))
                backup_data = {
                    "backup_id": i,
                    "timestamp": datetime.now().isoformat(),
                    "system": "review-gate-v2",
                    "data": data,
                    "mcp_integration": True,
                    "immediate_activation": True
                }
                backup_trigger.write_text(json.dumps(backup_data, indent=2, ensure_ascii=False), encoding='utf-8')
            
            return True
            
        except Exception as e:
            logger.error(safe_log(f"Failed to create trigger: {e}"))
            return False


    async def run(self):
        """Run the Review Gate server with web interface"""
        logger.info(safe_log("Starting Review Gate 2.0 MCP Server with Web Interface..."))
        
        # Start web server
        if WEB_SERVER_AVAILABLE and AIOHTTP_AVAILABLE:
            try:
                self.web_server = get_web_server(self.web_config)
                await self.web_server.start()
                logger.info(safe_log(f"Web interface ready at http://{self.web_config.host}:{self.web_config.port}"))
            except Exception as e:
                logger.error(safe_log(f"Failed to start web server: {e}"))
                logger.info(safe_log("Falling back to file-based communication only"))
        else:
            logger.warning(safe_log("Web server not available - using file-based communication only"))
            logger.info(safe_log("Install aiohttp for web interface: pip install aiohttp"))
        
        # Run MCP server
        async with stdio_server() as (read_stream, write_stream):
            logger.info(safe_log("MCP Server ACTIVE on stdio transport"))
            
            server_task = asyncio.create_task(
                self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )
            )
            
            shutdown_task = asyncio.create_task(self._monitor_shutdown())
            heartbeat_task = asyncio.create_task(self._heartbeat_logger())
            
            done, pending = await asyncio.wait(
                [server_task, shutdown_task, heartbeat_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Stop web server
            if self.web_server:
                await self.web_server.stop()
            
            if self.shutdown_requested:
                logger.info(safe_log(f"Server shutting down: {self.shutdown_reason}"))
            else:
                logger.info(safe_log("Server completed normally"))

    async def _heartbeat_logger(self):
        """Periodically update log file"""
        heartbeat_count = 0
        
        while not self.shutdown_requested:
            try:
                await asyncio.sleep(10)
                heartbeat_count += 1
                
                client_info = ""
                if self.web_server and self.web_server.is_running:
                    client_info = f", Web clients: {self.web_server.client_count}"
                
                logger.info(safe_log(f"Heartbeat #{heartbeat_count} - Server active{client_info}"))
                
            except Exception as e:
                logger.error(safe_log(f"Heartbeat error: {e}"))
                await asyncio.sleep(5)

    async def _monitor_shutdown(self):
        """Monitor for shutdown requests"""
        while not self.shutdown_requested:
            await asyncio.sleep(1)
        
        logger.info(safe_log("Performing cleanup..."))
        
        try:
            temp_files = [
                get_temp_path("review_gate_trigger.json"),
                get_temp_path("review_gate_trigger_0.json"),
                get_temp_path("review_gate_trigger_1.json"),
                get_temp_path("review_gate_trigger_2.json")
            ]
            for temp_file in temp_files:
                if Path(temp_file).exists():
                    Path(temp_file).unlink()
                    
        except Exception as e:
            logger.warning(safe_log(f"Cleanup warning: {e}"))
        
        return True


async def main():
    """Main entry point"""
    logger.info(safe_log("STARTING Review Gate v2 MCP Server with Web Interface..."))
    logger.info(safe_log(f"Python version: {sys.version}"))
    logger.info(safe_log(f"Platform: {sys.platform}"))
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Review Gate V2 MCP Server with Web Interface')
    parser.add_argument('--host', default='127.0.0.1', help='Web server host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8765, help='Web server port (default: 8765)')
    parser.add_argument('--no-browser', action='store_true', help='Do not auto-open browser')
    
    args, unknown = parser.parse_known_args()
    
    web_config = WebServerConfig(
        host=args.host,
        port=args.port,
        auto_open_browser=not args.no_browser
    ) if WEB_SERVER_AVAILABLE else None
    
    try:
        server = ReviewGateServerWeb(web_config)
        await server.run()
    except Exception as e:
        logger.error(safe_log(f"Fatal error: {e}"))
        import traceback
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info(safe_log("Server stopped by user"))
    except Exception as e:
        logger.error(safe_log(f"Server crashed: {e}"))
        sys.exit(1)

