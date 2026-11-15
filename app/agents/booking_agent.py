
import uuid
from datetime import datetime, timedelta

from sqlalchemy import update

from app.agents.base import BaseAgent
from app.database import SessionLocal
from app.models import Event, TicketCategory, Booking, Ticket


class BookingAgent(BaseAgent):

    def __init__(self):
        super().__init__("BookingAgent")
        self.max_tickets = 6

    def process_message(self, message):

        content = message.get("content", {})
        action = content.get("action")
        conversation_id = message.get("conversation_id")

        db = SessionLocal()

        try:
            if action == "book_tickets":

                quantity = content.get("quantity", 0)
                user_id = content.get("user_id")
                event_id = content.get("event_id")
                category_id = content.get("category_id")

                if not isinstance(quantity, int) or quantity < 1 or quantity > self.max_tickets:
                    return self.send_message(
                        message["sender"], "REFUSE",
                        {"reason": "Booking quantity must be between 1 and 6"},
                        conversation_id
                    )

                event = db.query(Event).filter(
                    Event.id == event_id,
                    Event.status == "published"
                ).first()

                category = db.query(TicketCategory).filter(
                    TicketCategory.id == category_id,
                    TicketCategory.event_id == event_id
                ).first()

                if not event or not category:
                    return self.send_message(
                        message["sender"], "REFUSE",
                        {"reason": "Event or ticket category is unavailable"},
                        conversation_id
                    )

                allocation = db.execute(
                    update(TicketCategory)
                    .where(
                        TicketCategory.id == category_id,
                        TicketCategory.sold + quantity <= TicketCategory.quantity
                    )
                    .values(sold=TicketCategory.sold + quantity)
                )

                if allocation.rowcount != 1:
                    db.rollback()

                    return self.send_message(
                        message["sender"], "REFUSE",
                        {"reason": "Not enough tickets available"},
                        conversation_id
                    )

                reference = "EVS-" + uuid.uuid4().hex[:12].upper()
                total = category.price * quantity

                booking = Booking(
                    user_id=user_id,
                    event_id=event_id,
                    category_id=category_id,
                    quantity=quantity,
                    total_amount=total,
                    payment_reference=reference,
                    status="confirmed",
                    created_at=datetime.utcnow()
                )

                db.add(booking)
                db.commit()
                db.refresh(booking)

                self.save_belief(
                    f"booking_{booking.id}",
                    {
                        "user_id": user_id,
                        "quantity": quantity,
                        "status": "confirmed"
                    }
                )

                return self.send_message(
                    message["sender"], "AGREE",
                    {
                        "reason": "Simulated payment successful",
                        "booking_id": booking.id,
                        "payment_reference": reference,
                        "quantity": quantity,
                        "total_amount": total,
                        "next_action": "issue_tickets"
                    },
                    conversation_id
                )

            elif action == "cancel_booking":

                booking_id = content.get("booking_id")
                user_id = content.get("user_id")

                booking = db.query(Booking).filter(
                    Booking.id == booking_id,
                    Booking.user_id == user_id
                ).with_for_update().first()

                if not booking or booking.status != "confirmed":
                    return self.send_message(
                        message["sender"], "REFUSE",
                        {"reason": "Booking does not exist or is already cancelled"},
                        conversation_id
                    )

                event = db.query(Event).filter(
                    Event.id == booking.event_id
                ).first()

                if not event:
                    return self.send_message(
                        message["sender"], "FAILURE",
                        {"reason": "Event information not found"},
                        conversation_id
                    )

                if event.status == "cancelled":
                    refund = booking.total_amount

                else:
                    hours_left = (
                        event.start_time - datetime.utcnow()
                    ).total_seconds() / 3600

                    if hours_left >= 48:
                        refund = booking.total_amount
                    elif hours_left >= 24:
                        refund = booking.total_amount * 0.5
                    else:
                        refund = 0

                booking.status = "cancelled"

                category = db.query(TicketCategory).filter(
                    TicketCategory.id == booking.category_id
                ).first()

                if category:
                    category.sold = max(
                        0, category.sold - booking.quantity
                    )

                tickets = db.query(Ticket).filter(
                    Ticket.booking_id == booking.id
                ).all()

                for ticket in tickets:
                    ticket.status = "cancelled"

                db.commit()

                return self.send_message(
                    message["sender"], "AGREE",
                    {
                        "reason": "Booking cancelled",
                        "booking_id": booking.id,
                        "refund_amount": round(refund, 2),
                        "refund_policy": "48+ hours: 100%, 24-48 hours: 50%, under 24 hours: 0%"
                    },
                    conversation_id
                )

            return self.send_message(
                message["sender"], "FAILURE",
                {"reason": "Unknown BookingAgent action"},
                conversation_id
            )

        except Exception as error:
            db.rollback()
            return self.send_message(
                message["sender"], "FAILURE",
                {"reason": str(error)},
                conversation_id
            )

        finally:
            db.close()
