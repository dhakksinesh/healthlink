
import logging
import os
from typing import Any

import pandas as pd

from app.database import get_db_manager, seed_doctors
from shared.config import Settings

logger = logging.getLogger("healthlink.seed")

def load_doctors_csv(path: str) -> list[dict[str, Any]]:

    df = pd.read_csv(path)
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    for record in records:
        if isinstance(record.get("experience_years"), (int, float)) and not isinstance(
            record.get("experience_years"), int
        ):
            record["experience_years"] = int(record["experience_years"])
        if isinstance(record.get("rating"), (int, float)):
            record["rating"] = float(record["rating"])
    return records

def seed_if_needed(settings: Settings) -> None:

    csv_file = settings.doctors_csv
    if not os.path.exists(csv_file):
        logger.warning(f"Doctors CSV not found: {csv_file} (DB will be empty)")
        return
    try:
        doctors_data = load_doctors_csv(csv_file)
        db_manager = get_db_manager(settings)
        with db_manager.session_scope() as session:
            seed_doctors(session, doctors_data)
    except Exception as e:
        logger.error(f"Doctor seeding failed: {e}", exc_info=True)
