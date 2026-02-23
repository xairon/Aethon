"""Mémoire longue — Stockage SQLite pour les souvenirs entre sessions."""

import logging
import sqlite3
import threading
import time
from pathlib import Path

from jarvis.config import MemoryConfig

log = logging.getLogger(__name__)


class MemoryStore:
    """Mémoire persistante simple basée sur SQLite.

    Stocke des faits extraits des conversations pour les réinjecter
    dans le contexte du LLM aux sessions suivantes.
    """

    def __init__(self, config: MemoryConfig):
        self.config = config
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def load(self):
        """Initialise la base de données."""
        with self._lock:
            db_path = Path(self.config.db_path)
            self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    created_at REAL NOT NULL,
                    importance INTEGER DEFAULT 1
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    session_id TEXT
                )
            """)
            self._conn.commit()
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_sort "
                "ON memories (importance DESC, created_at DESC)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_session "
                "ON conversations (session_id, created_at)"
            )
            self._conn.commit()
            count = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            log.info("Mémoire chargée: %d souvenirs stockés.", count)

    def add_memory(self, content: str, category: str = "general", importance: int = 1):
        """Ajoute un souvenir."""
        with self._lock:
            if not self._conn:
                return
            self._conn.execute(
                "INSERT INTO memories (content, category, created_at, importance) VALUES (?, ?, ?, ?)",
                (content, category, time.time(), importance),
            )
            self._conn.commit()
        log.debug("Nouveau souvenir: %s", content[:80])

    def get_recent_memories(self, limit: int | None = None) -> list[str]:
        """Récupère les souvenirs les plus récents et importants."""
        with self._lock:
            if not self._conn:
                return []
            n = limit or self.config.max_context_memories
            rows = self._conn.execute(
                "SELECT content FROM memories ORDER BY importance DESC, created_at DESC LIMIT ?",
                (n,),
            ).fetchall()
        return [r[0] for r in rows]

    def save_conversation_turn(self, role: str, content: str, session_id: str = ""):
        """Sauvegarde un tour de conversation."""
        with self._lock:
            if not self._conn:
                return
            self._conn.execute(
                "INSERT INTO conversations (role, content, created_at, session_id) VALUES (?, ?, ?, ?)",
                (role, content, time.time(), session_id),
            )
            self._conn.commit()

    def extract_memories_from_text(self, text: str) -> list[str]:
        """Extraction simple de faits depuis le texte."""
        facts = []
        markers = [
            "je m'appelle", "mon nom est", "j'habite", "je travaille",
            "j'aime", "je préfère", "je déteste",
            "je suis", "j'ai", "mon projet", "rappelle-toi", "souviens-toi",
            "n'oublie pas", "retiens",
        ]
        lower = text.lower()
        for marker in markers:
            if marker in lower:
                facts.append(text.strip())
                break
        return facts

    def process_user_message(self, text: str, session_id: str = ""):
        """Traite un message utilisateur : sauvegarde + extraction de mémoire."""
        self.save_conversation_turn("user", text, session_id)
        extracted = self.extract_memories_from_text(text)
        for fact in extracted:
            self.add_memory(fact, category="user_info", importance=2)

    def process_assistant_message(self, text: str, session_id: str = ""):
        """Sauvegarde une réponse assistant."""
        self.save_conversation_turn("assistant", text, session_id)

    def cleanup(self):
        """Ferme la connexion."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
