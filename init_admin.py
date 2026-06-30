"""Initialize admin user in the database."""

import sqlite3
from werkzeug.security import generate_password_hash

# Connection to database
conn = sqlite3.connect('idarati.db')
cursor = conn.cursor()

# Hash the password
password_hash = generate_password_hash("admin123", method="pbkdf2:sha256")

# Insert admin user
cursor.execute("""
    INSERT INTO dashboard_users (username, email, password_hash, is_admin)
    VALUES (?, ?, ?, ?)
""", ("admin", "admin@idarati.local", password_hash, 1))

conn.commit()

# Verify
cursor.execute("SELECT id, username, email, is_admin FROM dashboard_users")
rows = cursor.fetchall()
print("✓ Admin user created successfully!")
print(f"  Username: admin")
print(f"  Password: admin123")
print(f"  ID: {rows[0][0]}")

conn.close()
