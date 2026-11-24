
from datetime import datetime, timedelta

from app.agents.base import BaseAgent
from app.database import SessionLocal
from app.models import WaitlistEntry, TicketCategory, Event


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
            # Serialize offer allocation for this category on databases
            # that support row-level locks (e.g. PostgreSQL).
            category = db.query(TicketCategory).filter(
                TicketCategory.id == category_id
            ).with_for_update().first()

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

            event = db.query(Event).filter(
                Event.id == event_id,
                Event.status == "published"
            ).first()

            if not event:
                return {
                    "success": False,
                    "reason": "Event is not available for waitlisting"
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

        db = SessionLocal()
        try:
            entry = db.query(WaitlistEntry).filter(
                WaitlistEntry.id == entry_id
            ).first()

            queue_position = None
            if entry and entry.status == "waiting":
                queue_position = db.query(WaitlistEntry).filter(
                    WaitlistEntry.category_id == category_id,
                    WaitlistEntry.status == "waiting",
                    WaitlistEntry.id <= entry_id
                ).count()

            current_status = entry.status if entry else "waiting"
        finally:
            db.close()

        return {
            "success": True,
            "waitlist_id": entry_id,
            "status": current_status,
            "queue_position": queue_position,
            "message": (
                "A ticket offer is ready for you"
                if current_status == "offered"
                else "Added to the waiting list in first-come, first-served order"
            ),
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
            expired_for_notifications = []

            for entry in expired:

                entry.status = "expired"

                categories.add(entry.category_id)
                expired_for_notifications.append(
                    (entry.user_id, entry.id)
                )

            expired_count = len(expired)

            db.commit()

        except Exception:

            db.rollback()
            raise

        finally:
            db.close()

        # Tell attendees their claim window ended.
        for user_id, waitlist_id in expired_for_notifications:
            self.send_message(
                "NotificationAgent",
                "INFORM",
                {
                    "user_id": user_id,
                    "type": "waitlist_offer_expired",
                    "waitlist_id": waitlist_id,
                    "message": (
                        "Your 10-minute ticket offer expired. "
                        "The ticket has been offered to the next person in the queue."
                    )
                }
            )

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
