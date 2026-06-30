"""Ingest documents into the SQLite RAG database."""

import argparse
import os
from database.schema import init_db
from database.seed import seed


def ingest_directory(directory: str):
    from database.db import get_db
    with get_db() as conn:
        for root, _, files in os.walk(directory):
            for fname in files:
                if fname.endswith((".txt", ".md", ".pdf", ".docx")):
                    path = os.path.join(root, fname)
                    category = os.path.basename(root) or "general"
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    title = os.path.splitext(fname)[0]
                    conn.execute(
                        "INSERT INTO rag_chunks (category, title, content, source) VALUES (?, ?, ?, ?)",
                        (category, title, content[:5000], path),
                    )
                    print(f"  Ingested: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest RAG documents")
    parser.add_argument("--dir", default="./data/docs", help="Directory with documents")
    parser.add_argument("--seed", action="store_true", help="Also seed demo data")
    args = parser.parse_args()

    init_db()
    if args.seed:
        seed()
    if os.path.isdir(args.dir):
        ingest_directory(args.dir)
    print("Done.")
