"""Add mock data to the database for testing."""

import sqlite3
import json
from datetime import datetime, timedelta
import random

conn = sqlite3.connect('idarati.db')
cursor = conn.cursor()

# Mock data
intents = ["Renouvellement CNIE", "Plainte administrative", "Demande allocation", "Réclamation service", "Information"]
priorites = ["basse", "normale", "haute", "urgente"]
langues = ["fr", "ar", "en"]
canaux = ["chat", "email", "sms", "whatsapp", "portal"]
statuts = ["nouveau", "en_cours", "resolu", "ferme"]

mock_reclamations = [
    {
        "demande_brute": "Comment renouveler mon CNIE ?",
        "intent": "Renouvellement CNIE",
        "priorite": "normale",
        "quality_score": 0.92,
    },
    {
        "demande_brute": "J'ai une plainte concernant le service clientèle",
        "intent": "Plainte administrative",
        "priorite": "haute",
        "quality_score": 0.78,
    },
    {
        "demande_brute": "Quelle est la procédure pour une demande d'allocation ?",
        "intent": "Demande allocation",
        "priorite": "normale",
        "quality_score": 0.85,
    },
    {
        "demande_brute": "Le délai de traitement est trop long",
        "intent": "Réclamation service",
        "priorite": "haute",
        "quality_score": 0.88,
    },
    {
        "demande_brute": "J'ai besoin d'information sur les documents requis",
        "intent": "Information",
        "priorite": "basse",
        "quality_score": 0.91,
    },
    {
        "demande_brute": "Problème avec ma demande en ligne",
        "intent": "Plainte administrative",
        "priorite": "urgente",
        "quality_score": 0.65,
    },
    {
        "demande_brute": "Renouvellement permis de conduire",
        "intent": "Renouvellement CNIE",
        "priorite": "normale",
        "quality_score": 0.89,
    },
    {
        "demande_brute": "Suivi de ma demande d'allocation",
        "intent": "Demande allocation",
        "priorite": "normale",
        "quality_score": 0.76,
    },
]

# Insert mock data with dates spread over last 30 days
for i, rec in enumerate(mock_reclamations):
    days_ago = random.randint(0, 30)
    hours_ago = random.randint(0, 23)
    minutes_ago = random.randint(0, 59)
    
    created_at = (datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)).isoformat()
    
    audit_log = [
        {"node": "nlu", "timestamp": created_at, "status": "completed"},
        {"node": "routing", "timestamp": created_at, "status": "completed"},
        {"node": "rag", "timestamp": created_at, "status": "completed"},
    ]
    
    cursor.execute("""
        INSERT INTO submitted_reclamations 
        (session_id, user_id, demande_brute, intent, priorite, langue, canal_cible, 
         quality_score, processing_time_ms, audit_log_json, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        f"sess_{i:03d}_{random.randint(1000, 9999)}",
        f"user_{random.randint(100, 999)}",
        rec["demande_brute"],
        rec["intent"],
        rec["priorite"],
        random.choice(langues),
        random.choice(canaux),
        rec["quality_score"],
        random.randint(200000, 400000),  # 200-400 seconds (3-6 minutes)
        json.dumps(audit_log),
        random.choice(statuts),
        created_at,
        created_at
    ))

conn.commit()

# Verify
cursor.execute("SELECT COUNT(*) as cnt FROM submitted_reclamations")
count = cursor.fetchone()[0]
print(f"✓ {count} mock reclamations added!")

conn.close()
