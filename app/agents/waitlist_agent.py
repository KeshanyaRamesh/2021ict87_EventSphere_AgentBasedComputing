
from datetime import datetime, timedelta

from app.agents.base import BaseAgent
from app.database import SessionLocal
from app.models import WaitlistEntry, TicketCategory


class WaitlistAgent(BaseAgent):

    def __init__(self):
        super().__init__("WaitlistAgent")
        self.hold_minutes = 10

    # -------------------------------------------------
    # OFFER AVAILABLE TICKETS
    # -------------------------------------------------

    def offer_available(self, category_id):

        db = SessionLocal()
        offers = []

        try:
            category = db.query(TicketCategory).filter(
                TicketCategory.id == category_id
            ).first()

            if not category:
                return offers

            # Use UTC consistently for waitlist hold expiry.
            now = datetime.utcnow()

            active_holds = db.query(WaitlistEntry).filter(
                WaitlistEntry.category_id == category_id,
                WaitlistEntry.status == "offered",
                WaitlistEntry.hold_expires_at > now
            ).count()

            available = max(
                0,
                category.quantity - category.sold - active_holds
            )

            if available == 0:
                return offers

            # Select each waiting entry only once.
            waiting_entries = db.query(WaitlistEntry).filter(
                WaitlistEntry.category_id == category_id,
                WaitlistEntry.status == "waiting"
            ).order_by(
                WaitlistEntry.id.asc()
            ).limit(available).all()

            for entry in waiting_entries:

                entry.status = "offered"

                entry.hold_expires_at = (
                    now + timedelta(minutes=self.hold_minutes)
                )

                offers.append({
                    "user_id": entry.user_id,
                    "event_id": entry.event_id,
                    "category_id": category_id,
                    "waitlist_id": entry.id,
                    "expires_at": (
                        entry.hold_expires_at.isoformat()
                    ) + "Z"
                })

            db.commit()

        except Exception:

            db.rollback()
            raise

        finally:
            db.close()

        # Notify each selected attendee once.
        for offer in offers:

            self.send_message(
                "NotificationAgent",
                "INFORM",
                {
                    "type": "waitlist_offer",
                    **offer,
                    "message": (
                        "A ticket is available for you. "
                        "Please claim it within 10 minutes."
                    )
                }
            )

        return offers

    # -------------------------------------------------
    # JOIN WAITLIST
    # -------------------------------------------------

    def join_waitlist(self, user_id, event_id, category_id):

        db = SessionLocal()

        try:

            existing = db.query(WaitlistEntry).filter(
                WaitlistEntry.user_id == user_id,
                WaitlistEntry.category_id == category_id,
                WaitlistEntry.status.in_(
                    ["waiting", "offered"]
                )
            ).first()

            if existing:
                return {
                    "success": False,
                    "reason": "You are already in this waitlist"
                }

            category = db.query(TicketCategory).filter(
                TicketCategory.id == category_id,
                TicketCategory.event_id == event_id
            ).first()

            if not category:
                return {
                    "success": False,
                    "reason": "Ticket category not found"
                }

            entry = WaitlistEntry(
                user_id=user_id,
                event_id=event_id,
                category_id=category_id,
                status="waiting"
            )

            db.add(entry)
            db.commit()
            db.refresh(entry)

            entry_id = entry.id

        except Exception:

            db.rollback()
            raise

        finally:
            db.close()

        # Automatically offer tickets if available.
        offers = self.offer_available(category_id)

        return {
            "success": True,
            "waitlist_id": entry_id,
            "message": "Added to waitlist",
            "offers": offers
        }

    # -------------------------------------------------
    # EXPIRE UNCLAIMED OFFERS
    # -------------------------------------------------

    def expiry_sweep(self):

        db = SessionLocal()

        try:

            now = datetime.utcnow()

            expired = db.query(WaitlistEntry).filter(
                WaitlistEntry.status == "offered",
                WaitlistEntry.hold_expires_at <= now
            ).all()

            categories = set()

            for entry in expired:

                entry.status = "expired"

                categories.add(entry.category_id)

            expired_count = len(expired)

            db.commit()

        except Exception:

            db.rollback()
            raise

        finally:
            db.close()

        # Offer released tickets to the next waiting attendees.
        new_offers = []

        for category_id in categories:

            new_offers.extend(
                self.offer_available(category_id)
            )

        self.save_belief(
            "last_expiry_sweep",
            {
                "checked_at": datetime.utcnow().isoformat(),
                "expired_count": expired_count,
                "new_offers": len(new_offers)
            }
        )

        return {
            "expired_count": expired_count,
            "new_offers": len(new_offers)
        }

    # -------------------------------------------------
    # AGENT MESSAGE HANDLING
    # -------------------------------------------------

    def process_message(self, message):

        content = message.get("content", {})
        action = content.get("action")
        conversation_id = message.get("conversation_id")

        if action == "join_waitlist":

            result = self.join_waitlist(
                content.get("user_id"),
                content.get("event_id"),
                content.get("category_id")
            )

            return self.send_message(
                message["sender"],
                "AGREE" if result["success"] else "REFUSE",
                result,
                conversation_id
            )

        if action == "expiry_sweep":

            result = self.expiry_sweep()

            return self.send_message(
                message["sender"],
                "INFORM",
                result,
                conversation_id
            )

        if action == "release_seats":

            result = self.offer_available(
                content.get("category_id")
            )

            return self.send_message(
                message["sender"],
                "INFORM",
                {"offers": result},
                conversation_id
            )

        return self.send_message(
            message["sender"],
            "FAILURE",
            {
                "reason": "Unknown WaitlistAgent action"
            },
            conversation_id
        )
