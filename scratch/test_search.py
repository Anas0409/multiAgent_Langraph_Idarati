import sqlite3
import os

def test_search():
    db_path = "d:\\Project\\eIdarati_multiAgent_langraph\\idarati.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    query = "CNIE Casablanca"
    print(f"Searching for: {query}")
    
    try:
        rows = conn.execute("""
            SELECT p.titre FROM procedures p
            JOIN procedures_fts f ON p.id = f.rowid
            WHERE procedures_fts MATCH ?
            LIMIT 5
        """, (query,)).fetchall()
        
        if not rows:
            print("No results found with MATCH.")
            # Try simple LIKE
            rows_like = conn.execute("SELECT titre FROM procedures WHERE titre LIKE ?", (f"%{query}%",)).fetchall()
            print(f"Results with LIKE: {len(rows_like)}")
        else:
            for r in rows:
                print(f"- {r['titre']}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_search()
