
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.agents.base import MessageBus, PERFORMATIVES
from app.agents.booking_agent import BookingAgent
from app.agents.venue_agent import VenueAgent
from app.agents.ticket_agent import TicketAgent
from app.agents.waitlist_agent import WaitlistAgent
from app.agents.notification_agent import NotificationAgent
from app.database import SessionLocal
from app.models import (
    User, Venue, Event, TicketCategory, Booking, Ticket,
    AgentMessage,
)


@pytest.fixture
def records():
    db: Session = SessionLocal()

    user = User(
        full_name="Test Attendee",
        email="attendee@test.local",
        password_hash="test-hash",
        role="attendee",
    )

    venue = Venue(
        name="Main Hall",
        location="Campus",
        capacity=100,
        description="Test venue",
        hourly_rate=1000,
        available_for_hire=True,
    )

    db.add_all([user, venue])
    db.commit()
    db.refresh(user)
    db.refresh(venue)

    start = datetime.utcnow() + timedelta(days=2)

    event = Event(
        title="Test Event",
        category="Workshop",
        venue_id=venue.id,
        start_time=start,
        end_time=start + timedelta(hours=2),
        description="Test",
        status="published",
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    category = TicketCategory(
        event_id=event.id,
        name="General",
        price=500,
        quantity=2,
        sold=0,
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    ids = {
        "user": user.id,
        "venue": venue.id,
        "event": event.id,
        "category": category.id,
    }

    db.close()
    return ids


def message(action, content, sender="TestClient",
            conversation_id="test-conversation"):
    return {
        "sender": sender,
        "receiver": "Agent",
        "performative": "REQUEST",
        "content": {"action": action, **content},
        "conversation_id": conversation_id,
    }


def test_message_bus_accepts_all_required_performatives():
    assert PERFORMATIVES == {
        "REQUEST", "AGREE", "REFUSE",
        "PROPOSE", "INFORM", "FAILURE"
    }


def test_message_bus_rejects_unknown_performative():
    with pytest.raises(ValueError):
        MessageBus.send("A", "B", "MAYBE", {})


def test_message_bus_persists_conversation(records):
    sent = MessageBus.send(
        "A", "B", "INFORM",
        {"ok": True},
        "conversation-123",
    )

    assert sent["conversation_id"] == "conversation-123"

    db = SessionLocal()
    saved = db.query(AgentMessage).filter_by(
        conversation_id="conversation-123"
    ).one()

    assert saved.receiver == "B"
    assert saved.performative == "INFORM"
    db.close()


def test_booking_agent_refuses_quantity_over_six(records):
    result = BookingAgent().process_message(message(
        "book_tickets",
        {
            "quantity": 7,
            "user_id": records["user"],
            "event_id": records["event"],
            "category_id": records["category"],
        },
    ))

    assert result["performative"] == "REFUSE"
    assert "1 and 6" in result["content"]["reason"]


def test_booking_agent_allocates_within_inventory(records):
    result = BookingAgent().process_message(message(
        "book_tickets",
        {
            "quantity": 2,
            "user_id": records["user"],
            "event_id": records["event"],
            "category_id": records["category"],
        },
    ))

    assert result["performative"] == "AGREE"

    db = SessionLocal()
    category = db.get(TicketCategory, records["category"])
    assert category.sold == 2
    db.close()


def test_booking_agent_prevents_overbooking(records):
    agent = BookingAgent()

    payload = {
        "quantity": 2,
        "user_id": records["user"],
        "event_id": records["event"],
        "category_id": records["category"],
    }

    first = agent.process_message(message("book_tickets", payload))
    second = agent.process_message(message("book_tickets", payload))

    assert first["performative"] == "AGREE"
    assert second["performative"] == "REFUSE"


def test_venue_agent_accepts_free_slot(records):
    start = datetime.utcnow() + timedelta(days=10)

    result = VenueAgent().process_message(message(
        "check_hire",
        {
            "venue_id": records["venue"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=2)).isoformat(),
            "guest_count": 20,
        },
    ))

    assert result["performative"] == "AGREE"
    assert result["content"]["quoted_price"] == 2000


def test_venue_agent_refuses_guest_count_over_capacity(records):
    start = datetime.utcnow() + timedelta(days=10)

    result = VenueAgent().process_message(message(
        "check_hire",
        {
            "venue_id": records["venue"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=2)).isoformat(),
            "guest_count": 101,
        },
    ))

    assert result["performative"] == "REFUSE"


def test_venue_agent_proposes_alternatives_for_clash(records):
    start = datetime.utcnow() + timedelta(days=2)

    result = VenueAgent().process_message(message(
        "check_hire",
        {
            "venue_id": records["venue"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=2)).isoformat(),
            "guest_count": 20,
        },
    ))

    assert result["performative"] == "PROPOSE"
    assert result["content"]["reason"]
    assert isinstance(result["content"]["alternatives"], list)


def test_ticket_agent_issues_unique_codes(records):
    booking_result = BookingAgent().process_message(message(
        "book_tickets",
        {
            "quantity": 2,
            "user_id": records["user"],
            "event_id": records["event"],
            "category_id": records["category"],
        },
    ))

    booking_id = booking_result["content"]["booking_id"]

    result = TicketAgent().process_message(message(
        "issue_tickets",
        {"booking_id": booking_id},
    ))

    assert result["performative"] == "INFORM"

    codes = result["content"]["tickets"]
    assert len(codes) == 2
    assert len(set(codes)) == 2


def test_ticket_agent_rejects_unknown_ticket(records):
    result = TicketAgent().process_message(message(
        "scan_ticket",
        {
            "code": "not-a-real-ticket",
            "event_id": records["event"],
        },
    ))

    assert result["performative"] == "REFUSE"
    assert result["content"]["reason"] == "Invalid ticket code"


def test_waitlist_agent_adds_attendee_once(records):
    agent = WaitlistAgent()

    payload = {
        "user_id": records["user"],
        "event_id": records["event"],
        "category_id": records["category"],
    }

    first = agent.process_message(message("join_waitlist", payload))
    second = agent.process_message(message("join_waitlist", payload))

    assert first["performative"] == "AGREE"
    assert second["performative"] == "REFUSE"


def test_waitlist_expiry_sweep_persists_state(records):
    result = WaitlistAgent().expiry_sweep()

    assert result["expired_count"] == 0

    agent = WaitlistAgent()
    assert agent.get_belief("last_expiry_sweep")["expired_count"] == 0


def test_notification_agent_persists_user_notification(records):
    agent = NotificationAgent()

    result = agent.process_message({
        "performative": "INFORM",
        "sender": "BookingAgent",
        "conversation_id": "notify-test",
        "content": {
            "user_id": records["user"],
            "message": "Booking confirmed",
        },
    })

    assert result["success"] is True

    saved = agent.get_notifications(records["user"])

    assert saved[-1]["message"] == "Booking confirmed"
    assert saved[-1]["conversation_id"] == "notify-test"


def test_ticket_agent_admits_valid_ticket_once(records):
    db = SessionLocal()

    event = db.get(Event, records["event"])

    now = datetime.now(
        ZoneInfo("Asia/Colombo")
    ).replace(tzinfo=None)

    event.start_time = now - timedelta(minutes=30)
    event.end_time = now + timedelta(hours=2)

    booking = Booking(
        user_id=records["user"],
        event_id=event.id,
        category_id=records["category"],
        quantity=1,
        total_amount=500,
        payment_reference="EVS-TEST-ONE",
        status="confirmed",
        created_at=now,
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    ticket = Ticket(
        booking_id=booking.id,
        event_id=event.id,
        qr_code="unique-test-qr-code",
        status="valid",
        checked_in=False,
    )

    db.add(ticket)
    db.commit()
    db.close()

    result = TicketAgent().process_message(message(
        "scan_ticket",
        {
            "code": "unique-test-qr-code",
            "event_id": records["event"],
        },
    ))

    assert result["performative"] == "AGREE"
    assert result["content"]["admitted"] is True


def test_ticket_agent_rejects_second_check_in(records):
    db = SessionLocal()

    event = db.get(Event, records["event"])

    now = datetime.now(
        ZoneInfo("Asia/Colombo")
    ).replace(tzinfo=None)

    event.start_time = now - timedelta(minutes=30)
    event.end_time = now + timedelta(hours=2)

    booking = Booking(
        user_id=records["user"],
        event_id=event.id,
        category_id=records["category"],
        quantity=1,
        total_amount=500,
        payment_reference="EVS-TEST-TWO",
        status="confirmed",
        created_at=now,
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    ticket = Ticket(
        booking_id=booking.id,
        event_id=event.id,
        qr_code="already-used-qr-code",
        status="valid",
        checked_in=True,
    )

    db.add(ticket)
    db.commit()
    db.close()

    result = TicketAgent().process_message(message(
        "scan_ticket",
        {
            "code": "already-used-qr-code",
            "event_id": records["event"],
        },
    ))

    assert result["performative"] == "REFUSE"
    assert result["content"]["reason"] == "Ticket has already been used"


def test_ticket_agent_rejects_cancelled_ticket(records):
    db = SessionLocal()

    event = db.get(Event, records["event"])

    now = datetime.now(
        ZoneInfo("Asia/Colombo")
    ).replace(tzinfo=None)

    event.start_time = now - timedelta(minutes=30)
    event.end_time = now + timedelta(hours=2)

    booking = Booking(
        user_id=records["user"],
        event_id=event.id,
        category_id=records["category"],
        quantity=1,
        total_amount=500,
        payment_reference="EVS-TEST-THREE",
        status="cancelled",
        created_at=now,
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    ticket = Ticket(
        booking_id=booking.id,
        event_id=event.id,
        qr_code="cancelled-qr-code",
        status="cancelled",
        checked_in=False,
    )

    db.add(ticket)
    db.commit()
    db.close()

    result = TicketAgent().process_message(message(
        "scan_ticket",
        {
            "code": "cancelled-qr-code",
            "event_id": records["event"],
        },
    ))

    assert result["performative"] == "REFUSE"
    assert result["content"]["reason"] == "Ticket has been cancelled"
