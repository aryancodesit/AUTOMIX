import sqlite3
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "library.db"):
        """Initializes the SQLite database capable of handling 100k+ songs."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        # Track metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
                title TEXT,
                artist TEXT,
                duration_ms INTEGER
            )
        """)
        # Audio features for Smart Reorder
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AudioFeatures (
                track_id INTEGER PRIMARY KEY,
                bpm REAL,
                key INTEGER,
                mode INTEGER,
                camelot TEXT,
                energy REAL,
                drop_timestamp REAL DEFAULT 0.0,
                FOREIGN KEY(track_id) REFERENCES Tracks(id)
            )
        """)
        
        # Migration: Add drop_timestamp if upgrading from older version
        try:
            cursor.execute("SELECT drop_timestamp FROM AudioFeatures LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE AudioFeatures ADD COLUMN drop_timestamp REAL DEFAULT 0.0")
            
        self.conn.commit()

    def add_track(self, file_path: str, title: str, artist: str, duration_ms: int = 0) -> int:
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO Tracks (file_path, title, artist, duration_ms)
                VALUES (?, ?, ?, ?)
            """, (file_path, title, artist, duration_ms))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # File already exists, return existing ID
            cursor.execute("SELECT id FROM Tracks WHERE file_path = ?", (file_path,))
            return cursor.fetchone()['id']

    def add_audio_features(self, track_id: int, bpm: float, key: int, mode: int, camelot: str, energy: float, drop_timestamp: float = 0.0):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO AudioFeatures (track_id, bpm, key, mode, camelot, energy, drop_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (track_id, bpm, key, mode, camelot, energy, drop_timestamp))
        self.conn.commit()

    def get_all_tracks(self) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT t.id, t.file_path, t.title, t.artist, t.duration_ms, a.bpm, a.camelot, a.energy, a.drop_timestamp 
            FROM Tracks t
            LEFT JOIN AudioFeatures a ON t.id = a.track_id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        self.conn.close()
