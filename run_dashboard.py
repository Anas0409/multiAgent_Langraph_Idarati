"""Launch the Idarati admin dashboard on http://localhost:5000"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

from database.db import set_db_path
from database.schema import init_db
from config.settings import settings
from dashboard.app import app

set_db_path(settings.db_path)
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", 5000))
    print(f"\n  Idarati Admin Dashboard")
    print(f"  http://localhost:{port}\n")
    app.run(debug=False, port=port, host="0.0.0.0")
