from app.database import SessionLocal, create_tables
from app.models import User
from app.security import hash_password

DEMO_USERS = [
    {
        "full_name": "EventSphere Administrator",
        "email": "admin@eventsphere.demo",
        "password": "Admin@EventSphere2026!",
        "role": "admin",
    },
    {
        "full_name": "EventSphere Gate Staff",
        "email": "staff@eventsphere.demo",
        "password": "Staff@EventSphere2026!",
        "role": "staff",
    },
    {
        "full_name": "EventSphere Attendee",
        "email": "attendee@eventsphere.demo",
        "password": "Attendee@EventSphere2026!",
        "role": "attendee",
    },
]


def seed_demo_users():
    create_tables()
    db = SessionLocal()

    try:
        for details in DEMO_USERS:
            user = db.query(User).filter(
                User.email == details["email"]
            ).first()

            if user:
                user.full_name = details["full_name"]
                user.role = details["role"]
                user.password_hash = hash_password(details["password"])
                user.is_active = True
                print(f"Updated: {details['email']}")
            else:
                user = User(
                    full_name=details["full_name"],
                    email=details["email"],
                    password_hash=hash_password(details["password"]),
                    role=details["role"],
                    is_active=True,
                )
                db.add(user)
                print(f"Created: {details['email']}")

        db.commit()
        print("\nAll three EventSphere demo accounts are ready.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_users()