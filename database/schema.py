"""Database schema — single SQLite DB with multiple domain tables + FTS5."""

from database.db import get_db


def init_db():
    with get_db() as conn:
        # ── Zone C : User profiles ──────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                langue_pref TEXT DEFAULT 'fr',
                historique_resume TEXT DEFAULT '',
                preferences_json TEXT DEFAULT '{}',
                niveau_numerique TEXT DEFAULT 'moyen',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # ── Zone B : RAG domain tables ──────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reclamations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'reclamation',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conduite (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'conduite',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS juridique (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'juridique',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS politique (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'politique',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS divorce (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'divorce',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urbanisme (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'urbanisme',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS social (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'social',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS procedures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                titre TEXT NOT NULL,
                description TEXT NOT NULL,
                documents_requis TEXT DEFAULT '',
                conditions TEXT DEFAULT '',
                frais TEXT DEFAULT '',
                delais TEXT DEFAULT '',
                etapes TEXT DEFAULT '',
                administration_responsable TEXT DEFAULT '',
                recours TEXT DEFAULT '',
                base_legale TEXT DEFAULT '',
                url_source TEXT DEFAULT '',
                date_maj TEXT DEFAULT (datetime('now')),
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # ── Zone G : Audit & Feedback ───────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                node TEXT NOT NULL,
                latency_ms REAL DEFAULT 0,
                score_qualite REAL DEFAULT 0,
                rating_user INTEGER DEFAULT 0,
                comment TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # ── FTS5 virtual tables for full-text search ────────────
        for table in ("reclamations", "conduite", "juridique", "politique",
                      "divorce", "urbanisme", "social", "procedures"):
            try:
                conn.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS {table}_fts
                    USING fts5(title, content, content={table}, content_rowid=id)
                """)
            except Exception:
                pass  # already exists

        # For procedures table specifically, we might want different FTS columns if we don't map them to title/content
        # but let's keep it simple for now or map titre->title and description->content

        conn.execute("""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT DEFAULT '',
                state_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS submitted_reclamations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                user_id TEXT DEFAULT '',
                demande_brute TEXT DEFAULT '',
                intent TEXT DEFAULT 'inconnu',
                priorite TEXT DEFAULT 'normale',
                langue TEXT DEFAULT 'fr',
                canal_cible TEXT DEFAULT 'chat',
                quality_score REAL DEFAULT 0.0,
                processing_time_ms REAL DEFAULT 0.0,
                reponse_finale TEXT DEFAULT '',
                audit_log_json TEXT DEFAULT '[]',
                routing_plan TEXT DEFAULT '[]',
                documents_json TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Seed default admin user (admin / admin123)
        existing = conn.execute(
            "SELECT id FROM dashboard_users WHERE username='admin'"
        ).fetchone()
        if not existing:
            from werkzeug.security import generate_password_hash
            conn.execute(
                "INSERT INTO dashboard_users (username, email, password_hash, is_admin) VALUES (?,?,?,?)",
                ("admin", "admin@idarati.ma", generate_password_hash("admin123"), 1),
            )
