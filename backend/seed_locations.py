"""Seed the reference service-location hierarchy without demo data."""

from backend.database import SessionLocal
from backend.utils.service_locations import seed_service_locations


def main():
    db = SessionLocal()
    try:
        locations = seed_service_locations(db)
        db.commit()
        print(f"Service locations seeded successfully: {len(locations)} nodes.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
