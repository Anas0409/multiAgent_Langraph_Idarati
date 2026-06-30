import sqlite3
import json
import os

def export_to_json():
    db_path = os.path.join("d:\\Project\\eIdarati_multiAgent_langraph", "idarati.db")
    output_path = os.path.join("d:\\Project\\eIdarati_multiAgent_langraph", "procedures.json")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM procedures")
    rows = cursor.fetchall()
    
    data = [dict(row) for row in rows]
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    conn.close()
    print(f"Exported {len(data)} procedures to procedures.json")

if __name__ == "__main__":
    export_to_json()
