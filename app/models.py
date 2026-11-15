
from sqlalchemy import (
    Column, Integer, String, Boolean, Float,
    DateTime, ForeignKey, Text
)
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="attendee", nullable=False)
    is_active = Column(Boolean, default=True)


class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    location = Column(String(255), nullable=False)
    capacity = Column(Integer, nullable=False)
    description = Column(Text)
    image = Column(String(500))
    hourly_rate = Column(Float, default=0)
    available_for_hire = Column(Boolean, default=True)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    description = Column(Text)
    status = Column(String(20), default="draft")


class TicketCategory(Base):
    __tablename__ = "ticket_categories"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    sold = Column(Integer, default=0)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("ticket_categories.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=False)
    payment_reference = Column(String(100), unique=True)
    status = Column(String(20), default="confirmed")
    created_at = Column(DateTime, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    qr_code = Column(String(255), unique=True, nullable=False)
    status = Column(String(20), default="valid")
    checked_in = Column(Boolean, default=False)
    checked_in_at = Column(DateTime)


class VenueHireRequest(Base):
    __tablename__ = "venue_hire_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    purpose = Column(Text, nullable=False)
    guest_count = Column(Integer, nullable=False)
    quoted_price = Column(Float, default=0)
    status = Column(String(30), default="pending")


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("ticket_categories.id"), nullable=False)
    status = Column(String(20), default="waiting")
    hold_expires_at = Column(DateTime)


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String(100), nullable=False)
    receiver = Column(String(100), nullable=False)
    performative = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    conversation_id = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False)


class AgentState(Base):
    __tablename__ = "agent_states"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String(100), nullable=False)
    state_key = Column(String(150), nullable=False)
    state_value = Column(Text, nullable=False)