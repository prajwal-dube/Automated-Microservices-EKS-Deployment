import logging
import time
from .db import Database

if __name__ == "__main__":
    for attempt in range(60):
        try:
            Database().migrate()
            print("Schema initialized")
            break
        except Exception:
            if attempt == 59:
                raise
            logging.warning("Database not ready; retry %s/60", attempt + 1)
            time.sleep(2)
