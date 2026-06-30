"""Seed random data into all domain tables for demo/testing."""

import random
from database.db import get_db


_RECLAMATIONS = [
    ("Demande de carte nationale", "J'ai soumis ma demande de carte nationale d'identité il y a 3 mois au bureau de la commune. Je n'ai toujours pas reçu de réponse. Pouvez-vous m'aider ?"),
    ("Problème de passeport", "Mon passeport a expiré et j'ai besoin de le renouveler pour un voyage urgent. Quelles sont les démarches à suivre ?"),
    ("Registre civil bloqué", "Je n'arrive pas à obtenir un extrait d'acte de naissance pour mon enfant. Le service de l'état civil me demande des documents que j'ai déjà fournis."),
    ("Plainte contre une administration", "La mairie refuse de me délivrer un certificat de résidence alors que j'habite dans la commune depuis 10 ans."),
    ("Retard de traitement dossier", "Mon dossier de demande de subvention est en traitement depuis 6 mois sans aucune nouvelle."),
]

_CONDUITE = [
    ("Permis de conduire perdu", "J'ai perdu mon permis de conduire. Comment obtenir un duplicata et quel est le délai ?"),
    ("Contestation d'amende", "J'ai reçu une amende pour excès de vitesse alors que je respectais la limitation. Comment contester ?"),
    ("Changement de titulaire", "Je souhaite transférer mon permis de conduire d'une catégorie B vers une catégorie C. Quelles sont les conditions ?"),
    ("Permis international", "Je dois voyager à l'étranger pour le travail. Comment obtenir un permis de conduire international ?"),
    ("Visite médicale permis", "Mon permis de conduire arrive à expiration. Dois-je passer une visite médicale pour le renouvellement ?"),
]

_JURIDIQUE = [
    ("Délais de prescription", "Quels sont les délais de prescription pour une action en justice concernant un litige commercial ?"),
    ("Aide juridictionnelle", "Je souhaite saisir la justice mais je n'ai pas les moyens de payer un avocat. Puis-je bénéficier de l'aide juridictionnelle ?"),
    ("Procédure de saisie", "Un créancier menace de saisir mes biens. Quels sont mes droits et comment puis-je me défendre ?"),
    ("Tribunal compétent", "Je veux porter plainte contre une entreprise. Quel tribunal est compétent pour ce type de litige ?"),
    ("Exécution d'un jugement", "J'ai gagné mon procès mais le condamné ne paie pas. Comment faire exécuter le jugement ?"),
]

_POLITIQUE = [
    ("Aide au logement", "Quelles sont les aides disponibles pour les jeunes ménages souhaitant accéder à la propriété ?"),
    ("Subvention énergétique", "Je souhaite installer des panneaux solaires. Existe-t-il des subventions publiques pour cela ?"),
    ("Bourse d'études", "Mon enfant a été admis à l'université. Comment faire une demande de bourse d'études ?"),
    ("Aide à la création d'entreprise", "Je veux créer ma propre entreprise. Quels sont les programmes d'aide et d'accompagnement disponibles ?"),
    ("Allocation chômage", "J'ai perdu mon emploi. Comment faire une demande d'allocation chômage et quels sont les critères d'éligibilité ?"),
]

_DIVORCE = [
    ("Procédure de divorce", "Je souhaite divorcer de mon conjoint. Quelles sont les étapes et les documents nécessaires ?"),
    ("Pension alimentaire", "Mon ex-conjoint ne paie pas la pension alimentaire pour nos enfants. Que puis-je faire ?"),
    ("Garde d'enfants", "Nous sommes en procédure de divorce. Comment est décidée la garde des enfants ?"),
    ("Partage des biens", "Après le divorce, comment se fait le partage des biens communs ?"),
    ("Divorce à l'amiable", "Nous sommes d'accord pour divorcer. Quelle est la procédure la plus rapide et la moins coûteuse ?"),
]

_URBANISME = [
    ("Permis de construire", "Je souhaite construire une extension de ma maison. Comment obtenir un permis de construire ?"),
    ("Déclaration de travaux", "Dois-je faire une déclaration pour installer une véranda ? Quels sont les seuils ?"),
    ("Certificat d'urbanisme", "Je veux acheter un terrain. Comment obtenir un certificat d'urbanisme pour vérifier la constructibilité ?"),
    ("Division parcellaire", "Je souhaite diviser mon terrain en deux lots. Quelles sont les démarches à suivre ?"),
    ("Alignement et servitudes", "Mon voisin conteste la limite de propriété. Comment obtenir un plan d'alignement officiel ?"),
]

_SOCIAL = [
    ("Aide médicale", "Comment faire une demande d'aide médicale pour les personnes à faibles revenus ?"),
    ("Allocation familiale", "Je viens d'avoir un enfant. Comment déclarer la naissance pour bénéficier des allocations familiales ?"),
    ("Aide au transport", "Existe-t-il des aides pour le transport des personnes handicapées ?"),
    ("Carte de séjour", "Je suis ressortissant étranger marié à une citoyenne marocaine. Comment obtenir une carte de séjour ?"),
    ("Aide alimentaire", "Je traverse des difficultés financières. Comment bénéficier d'une aide alimentaire d'urgence ?"),
]


def seed():
    with get_db() as conn:
        tables = {
            "reclamations": _RECLAMATIONS,
            "conduite": _CONDUITE,
            "juridique": _JURIDIQUE,
            "politique": _POLITIQUE,
            "divorce": _DIVORCE,
            "urbanisme": _URBANISME,
            "social": _SOCIAL,
        }
        for table, rows in tables.items():
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count > 0:
                continue
            for title, content in rows:
                conn.execute(
                    f"INSERT INTO {table} (category, title, content) VALUES (?, ?, ?)",
                    (table, title, content),
                )
        # Seed RAG chunks from domain tables
        chunk_count = conn.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()[0]
        if chunk_count == 0:
            for table, rows in tables.items():
                for title, content in rows:
                    conn.execute(
                        "INSERT INTO rag_chunks (category, title, content) VALUES (?, ?, ?)",
                        (table, title, content),
                    )
        # Seed profiles
        profile_count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        if profile_count == 0:
            sample_users = [
                ("user_demo_001", "fr", "moyen", '{"canal":"chat"}'),
                ("user_demo_002", "ar", "faible", '{"canal":"whatsapp"}'),
                ("user_demo_003", "fr", "avance", '{"canal":"email"}'),
                ("user_demo_004", "en", "moyen", '{"canal":"portal"}'),
            ]
            for uid, lang, niveau, prefs in sample_users:
                conn.execute(
                    "INSERT INTO profiles (user_id, langue_pref, niveau_numerique, preferences_json) VALUES (?, ?, ?, ?)",
                    (uid, lang, niveau, prefs),
                )


if __name__ == "__main__":
    from database.schema import init_db
    init_db()
    seed()
    print("Database initialized and seeded successfully.")
