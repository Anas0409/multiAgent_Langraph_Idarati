"""Flask admin dashboard for Idarati v2 — with Auth, Dark Mode, Search, Notifications, i18n, Swagger."""

import csv
import json
import os
import sys
from functools import lru_cache
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import (Flask, Response, abort, jsonify, make_response,
                   redirect, render_template, request, send_file, url_for)
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from werkzeug.security import check_password_hash, generate_password_hash
from flasgger import Swagger

from config.settings import settings as cfg
from database.db import get_db
from dashboard.pdf_export import generate_pdf

# ── App ────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "idarati-v2-dev-secret-key")

# ── Flask-Login ────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login_page"
login_manager.login_message = "Veuillez vous connecter."

@login_manager.unauthorized_handler
def unauthorized():
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"error": "Unauthorized"}), 401
    return redirect(url_for("login_page", next=request.url))

# ── Swagger ────────────────────────────────────────────────────
swagger = Swagger(app, config={
    "headers": [],
    "specs": [{"endpoint": "apispec", "route": "/api/spec.json",
               "rule_filter": lambda rule: rule.rule.startswith("/api/"),
               "model_filter": lambda tag: True}],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs",
}, template={
    "info": {
        "title": "Idarati v2 API",
        "version": "2.0.0",
        "description": "API REST du dashboard Idarati — Réclamations administratives marocaines",
    },
    "consumes": ["application/json"],
    "produces": ["application/json"],
})

# ── User model ─────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, id, username, email, is_admin):
        self.id = str(id)
        self.username = username
        self.email = email
        self.is_admin = bool(is_admin)

@login_manager.user_loader
def load_user(user_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, email, is_admin FROM dashboard_users WHERE id=?",
            (user_id,)
        ).fetchone()
    if row:
        return User(row["id"], row["username"], row["email"], row["is_admin"])
    return None

# ── i18n ──────────────────────────────────────────────────────
@lru_cache(maxsize=8)
def _load_i18n(lang: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "i18n", f"{lang}.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

@app.route("/lang/<code>")
def set_lang(code):
    if code not in ("fr", "ar", "en"):
        code = "fr"
    resp = make_response(redirect(request.referrer or url_for("index")))
    resp.set_cookie("lang", code, max_age=365 * 24 * 3600, samesite="Lax")
    return resp

# ── Context processor ──────────────────────────────────────────
@app.context_processor
def inject_globals():
    lang = request.cookies.get("lang", "fr")
    if lang not in ("fr", "ar", "en"):
        lang = "fr"
    return {"T": _load_i18n(lang), "lang": lang, "cu": current_user}

# ── DB helpers ─────────────────────────────────────────────────
def _rows(sql: str, params=()):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

def _scalar(sql: str, params=(), default=0):
    with get_db() as conn:
        val = conn.execute(sql, params).fetchone()[0]
    return val if val is not None else default

# ── Period filter helper ────────────────────────────────────────
_PERIOD_SQL = {
    "7d":  "AND created_at >= DATE('now', '-7 days')",
    "30d": "AND created_at >= DATE('now', '-30 days')",
    "90d": "AND created_at >= DATE('now', '-90 days')",
}
def _period_clause(period: str) -> str:
    return _PERIOD_SQL.get(period, _PERIOD_SQL["7d"])


# ══════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, username, email, password_hash, is_admin FROM dashboard_users WHERE username=?",
                (username,)
            ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            user = User(row["id"], row["username"], row["email"], row["is_admin"])
            login_user(user, remember=True)
            nxt = request.args.get("next") or url_for("index")
            return redirect(nxt)
        error = "Identifiants incorrects."
    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login_page"))


# ══════════════════════════════════════════════════════════════
# API ROUTES  (Swagger-documented)
# ══════════════════════════════════════════════════════════════

@app.route("/api/search")
@login_required
def api_search():
    """
    Recherche globale dans les réclamations
    ---
    tags:
      - Réclamations
    parameters:
      - name: q
        in: query
        type: string
        required: true
        description: Terme de recherche (minimum 2 caractères)
    responses:
      200:
        description: Liste de réclamations correspondantes
        schema:
          type: array
          items:
            type: object
            properties:
              session_id: {type: string}
              demande_brute: {type: string}
              intent: {type: string}
              priorite: {type: string}
              quality_score: {type: number}
      401:
        description: Non authentifié
    """
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    pattern = f"%{q}%"
    rows = _rows("""
        SELECT session_id, demande_brute, intent, priorite, quality_score
        FROM submitted_reclamations
        WHERE demande_brute LIKE ? OR intent LIKE ? OR session_id LIKE ?
        ORDER BY created_at DESC LIMIT 8
    """, (pattern, pattern, pattern))
    return jsonify(rows)


@app.route("/api/notifications")
@login_required
def api_notifications():
    """
    Récupère les dernières réclamations pour les notifications
    ---
    tags:
      - Notifications
    responses:
      200:
        description: Notifications récentes
        schema:
          type: object
          properties:
            count: {type: integer, description: Nombre de réclamations dans la dernière heure}
            items:
              type: array
              items:
                type: object
      401:
        description: Non authentifié
    """
    recent = _rows("""
        SELECT session_id, intent, priorite, quality_score, created_at
        FROM submitted_reclamations
        ORDER BY created_at DESC LIMIT 5
    """)
    unread = _scalar("""
        SELECT COUNT(*) FROM submitted_reclamations
        WHERE created_at >= datetime('now', '-1 hour')
    """)
    return jsonify({"count": unread, "items": recent})


@app.route("/api/reclamations")
@login_required
def api_reclamations():
    """
    Liste paginée des réclamations
    ---
    tags:
      - Réclamations
    parameters:
      - name: intent
        in: query
        type: string
        description: Filtrer par intent (reclamation, procedure, info, renvoi)
      - name: period
        in: query
        type: string
        description: Période (7d, 30d, 90d)
        default: "all"
      - name: limit
        in: query
        type: integer
        default: 50
    responses:
      200:
        description: Liste des réclamations
      401:
        description: Non authentifié
    """
    intent = request.args.get("intent", "")
    period = request.args.get("period", "all")
    limit  = min(int(request.args.get("limit", 50)), 200)
    where, params = "WHERE 1=1", []
    if intent:
        where += " AND intent=?"; params.append(intent)
    if period in _PERIOD_SQL:
        where += f" {_period_clause(period)}"
    rows = _rows(
        f"SELECT session_id, intent, priorite, quality_score, processing_time_ms, created_at "
        f"FROM submitted_reclamations {where} ORDER BY created_at DESC LIMIT {limit}",
        params,
    )
    return jsonify(rows)


@app.route("/api/stats")
@login_required
def api_stats():
    """
    Statistiques globales du système
    ---
    tags:
      - Stats
    responses:
      200:
        description: KPIs globaux
        schema:
          type: object
          properties:
            total: {type: integer}
            avg_quality: {type: number}
            success_rate: {type: number}
            avg_time_ms: {type: number}
    """
    total = _scalar("SELECT COUNT(*) FROM submitted_reclamations")
    avg_q = _scalar("SELECT AVG(quality_score) FROM submitted_reclamations WHERE quality_score > 0") or 0
    avg_t = _scalar("SELECT AVG(processing_time_ms) FROM submitted_reclamations WHERE processing_time_ms > 0") or 0
    sn    = _scalar("SELECT COUNT(*) FROM submitted_reclamations WHERE quality_score >= 0.85")
    return jsonify({
        "total": total,
        "avg_quality": round(avg_q * 100, 1),
        "success_rate": round(sn / total * 100, 1) if total else 0,
        "avg_time_ms": round(avg_t, 0),
    })


# ══════════════════════════════════════════════════════════════
# PAGE ROUTES  (all @login_required)
# ══════════════════════════════════════════════════════════════

@app.route("/")
@login_required
def index():
    period = request.args.get("period", "7d")
    pc = _period_clause(period)

    total      = _scalar("SELECT COUNT(*) FROM submitted_reclamations")
    avg_q      = _scalar("SELECT AVG(quality_score) FROM submitted_reclamations WHERE quality_score > 0") or 0
    avg_t      = _scalar("SELECT AVG(processing_time_ms) FROM submitted_reclamations WHERE processing_time_ms > 0") or 0
    success_n  = _scalar("SELECT COUNT(*) FROM submitted_reclamations WHERE quality_score >= 0.85")
    success_pct = round(success_n / total * 100, 1) if total else 0

    by_intent   = _rows(f"SELECT intent, COUNT(*) AS cnt FROM submitted_reclamations WHERE 1=1 {pc} GROUP BY intent ORDER BY cnt DESC")
    by_priorite = _rows(f"SELECT priorite, COUNT(*) AS cnt FROM submitted_reclamations WHERE 1=1 {pc} GROUP BY priorite ORDER BY cnt DESC")
    daily       = _rows(f"""
        SELECT DATE(created_at) AS day, COUNT(*) AS cnt, ROUND(AVG(quality_score)*100,1) AS avg_q
        FROM submitted_reclamations WHERE 1=1 {pc}
        GROUP BY DATE(created_at) ORDER BY day
    """)
    recent = _rows("SELECT * FROM submitted_reclamations ORDER BY created_at DESC LIMIT 8")

    return render_template("index.html",
        total=total, avg_quality=round(avg_q * 100, 1),
        avg_time_ms=round(avg_t, 0), success_pct=success_pct,
        by_intent=by_intent, by_priorite=by_priorite,
        daily=daily, recent=recent, period=period,
    )


@app.route("/reclamations")
@login_required
def reclamations():
    intent_filter = request.args.get("intent", "")
    if intent_filter:
        rows = _rows("SELECT * FROM submitted_reclamations WHERE intent=? ORDER BY created_at DESC", (intent_filter,))
    else:
        rows = _rows("SELECT * FROM submitted_reclamations ORDER BY created_at DESC")
    return render_template("reclamations.html", rows=rows, intent_filter=intent_filter)


@app.route("/reclamation/<path:session_id>")
@login_required
def detail(session_id):
    rows = _rows("SELECT * FROM submitted_reclamations WHERE session_id=?", (session_id,))
    if not rows:
        abort(404)
    data = rows[0]
    data["audit_log"]    = json.loads(data.get("audit_log_json") or "[]")
    data["routing_plan"] = json.loads(data.get("routing_plan") or "[]")
    data["documents"]    = json.loads(data.get("documents_json") or "[]")
    return render_template("detail.html", r=data)


@app.route("/reclamation/<path:session_id>/pdf")
@login_required
def export_pdf(session_id):
    rows = _rows("SELECT * FROM submitted_reclamations WHERE session_id=?", (session_id,))
    if not rows:
        abort(404)
    data = rows[0]
    data["audit_log"]          = json.loads(data.get("audit_log_json") or "[]")
    data["routing_plan"]       = json.loads(data.get("routing_plan") or "[]")
    data["documents_retrieved"] = json.loads(data.get("documents_json") or "[]")
    pdf_bytes = generate_pdf(data)
    return Response(pdf_bytes, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="idarati_{session_id[:8]}.pdf"'})


@app.route("/analytics")
@login_required
def analytics():
    period = request.args.get("period", "30d")
    pc = _period_clause(period)

    total     = _scalar("SELECT COUNT(*) FROM submitted_reclamations")
    avg_q     = _scalar("SELECT AVG(quality_score) FROM submitted_reclamations WHERE quality_score > 0") or 0
    avg_t     = _scalar("SELECT AVG(processing_time_ms) FROM submitted_reclamations WHERE processing_time_ms > 0") or 0
    success_n = _scalar("SELECT COUNT(*) FROM submitted_reclamations WHERE quality_score >= 0.85")

    by_intent_detail = _rows(f"""
        SELECT intent, COUNT(*) AS cnt, ROUND(AVG(quality_score)*100,1) AS avg_q,
               ROUND(AVG(processing_time_ms)/1000.0,2) AS avg_t_sec
        FROM submitted_reclamations WHERE 1=1 {pc} GROUP BY intent ORDER BY cnt DESC
    """)
    by_langue = _rows(f"SELECT langue, COUNT(*) AS cnt FROM submitted_reclamations WHERE 1=1 {pc} GROUP BY langue ORDER BY cnt DESC")
    by_canal  = _rows(f"SELECT canal_cible, COUNT(*) AS cnt FROM submitted_reclamations WHERE 1=1 {pc} GROUP BY canal_cible ORDER BY cnt DESC")
    daily_n   = _rows(f"""
        SELECT DATE(created_at) AS day, COUNT(*) AS cnt, ROUND(AVG(quality_score)*100,1) AS avg_q
        FROM submitted_reclamations WHERE 1=1 {pc}
        GROUP BY DATE(created_at) ORDER BY day
    """)
    quality_bins = _rows("""
        SELECT CASE WHEN quality_score >= 0.85 THEN 'Excellent' WHEN quality_score >= 0.70 THEN 'Bon'
                    WHEN quality_score >= 0.50 THEN 'Moyen' ELSE 'Faible' END AS label, COUNT(*) AS cnt
        FROM submitted_reclamations WHERE quality_score > 0 GROUP BY label
    """)
    return render_template("analytics.html",
        total=total, avg_quality=round(avg_q * 100, 1),
        avg_time_ms=round(avg_t, 0), success_n=success_n,
        by_intent_detail=by_intent_detail, by_langue=by_langue,
        by_canal=by_canal, daily_30=daily_n, quality_bins=quality_bins, period=period,
    )


@app.route("/users")
@login_required
def users():
    profiles = _rows("SELECT * FROM profiles ORDER BY created_at DESC")
    return render_template("users.html", profiles=profiles)


@app.route("/users/add", methods=["POST"])
@login_required
def users_add():
    uid = request.form.get("user_id", "").strip()
    if uid:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO profiles (user_id, langue_pref, niveau_numerique) VALUES (?,?,?)",
                (uid, request.form.get("langue_pref", "fr"), request.form.get("niveau_numerique", "moyen")),
            )
    return redirect(url_for("users"))


@app.route("/users/<path:user_id>/edit", methods=["POST"])
@login_required
def users_edit(user_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE profiles SET langue_pref=?, niveau_numerique=?, updated_at=datetime('now') WHERE user_id=?",
            (request.form.get("langue_pref", "fr"), request.form.get("niveau_numerique", "moyen"), user_id),
        )
    return redirect(url_for("users"))


@app.route("/users/<path:user_id>/delete", methods=["POST"])
@login_required
def users_delete(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM profiles WHERE user_id=?", (user_id,))
    return redirect(url_for("users"))


@app.route("/logs")
@login_required
def logs():
    node_filter = request.args.get("node", "")
    date_from   = request.args.get("from", "")
    date_to     = request.args.get("to", "")
    where, params = "WHERE 1=1", []
    if date_from:
        where += " AND created_at >= ?"; params.append(date_from)
    if date_to:
        where += " AND created_at <= ?"; params.append(date_to + " 23:59:59")
    sessions = _rows(
        f"SELECT session_id, user_id, intent, quality_score, audit_log_json, created_at "
        f"FROM submitted_reclamations {where} ORDER BY created_at DESC LIMIT 100", params,
    )
    all_logs = []
    for s in sessions:
        try:
            for e in json.loads(s.get("audit_log_json") or "[]"):
                if not node_filter or node_filter.lower() in e.get("node", "").lower():
                    all_logs.append({
                        "session_id": s["session_id"][:12] + "…", "intent": s["intent"],
                        "quality": s["quality_score"], "created_at": s["created_at"],
                        "node": e.get("node", ""),
                        "detail": {k: v for k, v in e.items() if k not in ("node", "ts")},
                    })
        except Exception:
            pass
    distinct_nodes = sorted({log["node"] for log in all_logs})
    return render_template("logs.html", logs=all_logs[:500], distinct_nodes=distinct_nodes,
        node_filter=node_filter, date_from=date_from, date_to=date_to, total_sessions=len(sessions))


@app.route("/rapports")
@login_required
def rapports():
    total     = _scalar("SELECT COUNT(*) FROM submitted_reclamations")
    success_n = _scalar("SELECT COUNT(*) FROM submitted_reclamations WHERE quality_score >= 0.85")
    avg_q     = _scalar("SELECT AVG(quality_score) FROM submitted_reclamations WHERE quality_score > 0") or 0
    by_intent = _rows("SELECT intent, COUNT(*) AS cnt FROM submitted_reclamations GROUP BY intent ORDER BY cnt DESC")
    recent    = _rows("SELECT session_id, user_id, intent, priorite, quality_score, created_at FROM submitted_reclamations ORDER BY created_at DESC LIMIT 50")
    return render_template("rapports.html", total=total, success_n=success_n,
        avg_quality=round(avg_q * 100, 1), by_intent=by_intent, recent=recent)


@app.route("/rapports/export/csv")
@login_required
def rapports_export_csv():
    rows = _rows("""
        SELECT session_id, user_id, demande_brute, intent, priorite, langue,
               canal_cible, quality_score, processing_time_ms, created_at
        FROM submitted_reclamations ORDER BY created_at DESC
    """)
    si = StringIO()
    if rows:
        writer = csv.DictWriter(si, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    output = "﻿" + si.getvalue()
    return Response(output, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="idarati_reclamations.csv"'})


@app.route("/parametres")
@login_required
def parametres():
    db_stats = {
        "submitted_reclamations": _scalar("SELECT COUNT(*) FROM submitted_reclamations"),
        "profiles":               _scalar("SELECT COUNT(*) FROM profiles"),
        "audit_feedback":         _scalar("SELECT COUNT(*) FROM audit_feedback"),
        "rag_chunks":             _scalar("SELECT COUNT(*) FROM rag_chunks"),
        "procedures":             _scalar("SELECT COUNT(*) FROM procedures"),
        "dashboard_users":        _scalar("SELECT COUNT(*) FROM dashboard_users"),
    }
    return render_template("parametres.html", cfg=cfg, db_stats=db_stats)
