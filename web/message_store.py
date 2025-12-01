#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Review Gate V2 - Message Storage Module
独立的SQLite消息存储和检索模块
"""

import sqlite3
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class MessageRecord:
    """Represents a stored message"""
    id: str
    trigger_id: str
    message_type: str  # 'system', 'user', 'plain'
    content: str
    timestamp: str
    date: str  # YYYY-MM-DD format for archiving
    has_attachments: bool = False
    attachments: List[dict] = field(default_factory=list)


class MessageStorage:
    """Message storage and retrieval system"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or 'messages.db'
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    trigger_id TEXT,
                    message_type TEXT,
                    content TEXT,
                    timestamp TEXT,
                    date TEXT,
                    has_attachments INTEGER DEFAULT 0,
                    attachments TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_date ON messages(date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trigger_id ON messages(trigger_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)')
            conn.commit()

    def save_message(self, message: MessageRecord):
        """Save a message to the database"""
        try:
            import json
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO messages
                    (id, trigger_id, message_type, content, timestamp, date, has_attachments, attachments)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    message.id,
                    message.trigger_id,
                    message.message_type,
                    message.content,
                    message.timestamp,
                    message.date,
                    1 if message.has_attachments else 0,
                    json.dumps(message.attachments, ensure_ascii=False) if message.attachments else None
                ))
                conn.commit()
        except Exception as e:
            print(f"Failed to save message: {e}")

    def get_messages_by_date(self, target_date: str, limit: int = 100) -> List[MessageRecord]:
        """Get messages for a specific date"""
        try:
            import json
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT id, trigger_id, message_type, content, timestamp, date, has_attachments, attachments
                    FROM messages
                    WHERE date = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (target_date, limit))

                messages = []
                for row in cursor.fetchall():
                    messages.append(MessageRecord(
                        id=row[0],
                        trigger_id=row[1],
                        message_type=row[2],
                        content=row[3],
                        timestamp=row[4],
                        date=row[5],
                        has_attachments=bool(row[6]),
                        attachments=json.loads(row[7]) if row[7] else []
                    ))
                return messages
        except Exception as e:
            print(f"Failed to get messages by date: {e}")
            return []

    def get_available_dates(self) -> List[str]:
        """Get list of available dates with messages"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT DISTINCT date FROM messages
                    ORDER BY date DESC
                ''')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Failed to get available dates: {e}")
            return []

    def search_messages(self, query: str, limit: int = 50) -> List[MessageRecord]:
        """Search messages by content"""
        try:
            import json
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT id, trigger_id, message_type, content, timestamp, date, has_attachments, attachments
                    FROM messages
                    WHERE content LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (f'%{query}%', limit))

                messages = []
                for row in cursor.fetchall():
                    messages.append(MessageRecord(
                        id=row[0],
                        trigger_id=row[1],
                        message_type=row[2],
                        content=row[3],
                        timestamp=row[4],
                        date=row[5],
                        has_attachments=bool(row[6]),
                        attachments=json.loads(row[7]) if row[7] else []
                    ))
                return messages
        except Exception as e:
            print(f"Failed to search messages: {e}")
            return []

    def get_recent_messages(self, limit: int = 50) -> List[MessageRecord]:
        """Get most recent messages"""
        try:
            import json
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT id, trigger_id, message_type, content, timestamp, date, has_attachments, attachments
                    FROM messages
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))

                messages = []
                for row in cursor.fetchall():
                    messages.append(MessageRecord(
                        id=row[0],
                        trigger_id=row[1],
                        message_type=row[2],
                        content=row[3],
                        timestamp=row[4],
                        date=row[5],
                        has_attachments=bool(row[6]),
                        attachments=json.loads(row[7]) if row[7] else []
                    ))
                return messages
        except Exception as e:
            print(f"Failed to get recent messages: {e}")
            return []
