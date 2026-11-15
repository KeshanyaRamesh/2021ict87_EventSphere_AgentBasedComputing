
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.agents.base import BaseAgent
from app.database import SessionLocal
from app.models import Booking, Ticket, Event


# EventSphere uses Sri Lankan local time for event scheduling.
SRI_LANKA_TIMEZONE = ZoneInfo("Asia/Colombo")


def get_local_time():
    """Return current Sri Lankan time without timezone information."""
    return datetime.now(SRI_LANKA_TIMEZONE).replace(tzinfo=None)


class TicketAgent(BaseAgent):

    def __init__(self):
        super().__init__("TicketAgent")

    # -------------------------------------------------
    # ISSUE TICKETS
    # -------------------------------------------------

    def issue_tickets(self, booking_id):

        db = SessionLocal()

        try:
            booking = db.query(Booking).filter(
                Booking.id == booking_id,
                Booking.status == "confirmed"
            ).first()

            if not booking:
                return {
                    "success": False,
                    "reason": "Confirmed booking not found"
                }

            existing = db.query(Ticket).filter(
                Ticket.booking_id == booking_id
            ).count()

            if existing > 0:
                return {
                    "success": False,
                    "reason": "Tickets have already been issued"
                }

            issued = []

            for _ in range(booking.quantity):

                code = secrets.token_urlsafe(32)

                ticket = Ticket(
                    booking_id=booking.id,
                    event_id=booking.event_id,
                    qr_code=code,
                    status="valid",
                    checked_in=False
                )

                db.add(ticket)
                issued.append(code)

            db.commit()

            self.save_belief(
                f"issued_booking_{booking_id}",
                {
                    "ticket_count": len(issued),
                    "issued": True
                }
            )

            return {
                "success": True,
                "booking_id": booking_id,
                "tickets": issued
            }

        except Exception as error:

            db.rollback()

            return {
                "success": False,
                "reason": str(error)
            }

        finally:
            db.close()

    # -------------------------------------------------
    # SCAN TICKET
    # -------------------------------------------------

    def scan_ticket(self, code, event_id):

        db = SessionLocal()

        try:

            # 1. Find ticket using QR code
            ticket = db.query(Ticket).filter(
                Ticket.qr_code == code
            ).first()

            if not ticket:
                return {
                    "admitted": False,
                    "reason": "Invalid ticket code"
                }

            # 2. Verify event ownership
            if ticket.event_id != event_id:
                return {
                    "admitted": False,
                    "reason": "Ticket belongs to another event"
                }

            # 3. Check cancellation
            if ticket.status == "cancelled":
                return {
                    "admitted": False,
                    "reason": "Ticket has been cancelled"
                }

            # 4. Prevent duplicate QR scanning
            if ticket.checked_in:
                return {
                    "admitted": False,
                    "reason": "Ticket has already been used"
                }

            # 5. Verify ticket status
            if ticket.status != "valid":
                return {
                    "admitted": False,
                    "reason": "Ticket is not valid"
                }

            # 6. Find event
            event = db.query(Event).filter(
                Event.id == event_id
            ).first()

            if not event:
                return {
                    "admitted": False,
                    "reason": "Event not found"
                }

            # 7. Get current Sri Lankan local time
            now = get_local_time()

            # 8. Allow check-in from 2 hours before event start
            check_in_start = (
                event.start_time - timedelta(hours=2)
            )

            # 9. Validate check-in window
            if now < check_in_start or now > event.end_time:

                return {
                    "admitted": False,
                    "reason": "Outside permitted check-in time",
                    "current_time": now.isoformat(),
                    "check_in_start": check_in_start.isoformat(),
                    "event_end": event.end_time.isoformat()
                }

            # 10. Successfully check in ticket
            ticket.checked_in = True
            ticket.checked_in_at = now

            db.commit()

            # 11. Save successful scan information
            self.save_belief(
                f"scan_count_{ticket.id}",
                1
            )

            return {
                "admitted": True,
                "reason": "Ticket accepted. Welcome!",
                "ticket_id": ticket.id,
                "event_id": event.id,
                "checked_in": True,
                "checked_in_at": now.isoformat()
            }

        except Exception as error:

            db.rollback()

            return {
                "admitted": False,
                "reason": str(error)
            }

        finally:
            db.close()

    # -------------------------------------------------
    # AGENT MESSAGE HANDLING
    # -------------------------------------------------

    def process_message(self, message):

        content = message.get("content", {})
        action = content.get("action")
        conversation_id = message.get("conversation_id")

        if action == "issue_tickets":

            result = self.issue_tickets(
                content.get("booking_id")
            )

            return self.send_message(
                message["sender"],
                "INFORM" if result["success"] else "FAILURE",
                result,
                conversation_id
            )

        if action == "scan_ticket":

            result = self.scan_ticket(
                content.get("code"),
                content.get("event_id")
            )

            return self.send_message(
                message["sender"],
                "AGREE" if result["admitted"] else "REFUSE",
                result,
                conversation_id
            )

        return self.send_message(
            message["sender"],
            "FAILURE",
            {
                "reason": "Unknown TicketAgent action"
            },
            conversation_id
        )
