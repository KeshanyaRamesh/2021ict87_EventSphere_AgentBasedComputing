
import asyncio
import base64
import io
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import qrcode
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db, create_tables
from app.models import (
    User, Venue, Event, TicketCategory,
    Booking, Ticket, AgentMessage, VenueHireRequest, WaitlistEntry
)
from app.schemas import (
    UserCreate, UserLogin, TokenResponse,
    VenueCreate, EventWithTicketsCreate,
    BookingCreate, CheckInRequest,
    WaitlistRequest, VenueHireCreate
)
from app.security import (
    hash_password, verify_password,
    create_access_token, decode_access_token
)

from app.agents.base import MessageBus
from app.agents.venue_agent import VenueAgent
from app.agents.booking_agent import BookingAgent
from app.agents.ticket_agent import TicketAgent
from app.agents.waitlist_agent import WaitlistAgent
from app.agents.notification_agent import NotificationAgent


# -------------------------------------------------
# PROJECT PATHS AND STATIC FILES
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Create directories if they do not exist.
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------
# AGENT INSTANCES
# -------------------------------------------------

venue_agent = VenueAgent()
booking_agent = BookingAgent()
ticket_agent = TicketAgent()
waitlist_agent = WaitlistAgent()
notification_agent = NotificationAgent()


# -------------------------------------------------
# AUTOMATIC WAITLIST SCHEDULER
# -------------------------------------------------

async def waitlist_scheduler():
    while True:
        try:
            waitlist_agent.expiry_sweep()
            notification_agent.process_inbox()
        except Exception as error:
            print("Waitlist scheduler error:", error)

        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()

    scheduler = asyncio.create_task(waitlist_scheduler())

    yield

    scheduler.cancel()

    try:
        await scheduler
    except asyncio.CancelledError:
        pass


# -------------------------------------------------
# FASTAPI APPLICATION
# -------------------------------------------------

app = FastAPI(
    title="EventSphere API",
    description="University Event and Venue Booking Multi-Agent System",
    version="1.0.0",
    lifespan=lifespan
)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static"
)


# -------------------------------------------------
# AUTHENTICATION
# -------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login"
)


def authenticate_user(email: str, password: str, db: Session):
    user = db.query(User).filter(
        User.email == email,
        User.is_active.is_(True)
    ).first()

    if not user or not verify_password(
        password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


def create_user_token(user: User):
    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired login token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.is_active.is_(True)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


def require_role(*roles):
    def role_checker(
        user: User = Depends(get_current_user)
    ):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource"
            )

        return user

    return role_checker


# -------------------------------------------------
# AGENT MESSAGE DELIVERY
# -------------------------------------------------

def deliver_message(agent, sender, content):
    """
    Send a structured message through the message bus.
    The message bus records the communication before
    the receiving agent processes the message.
    """

    message = MessageBus.send(
        sender,
        agent.name,
        "REQUEST",
        content
    )

    return agent.process_message(message)


def notify_user(
    user_id: int,
    message: str,
    notification_type: str = "general",
    metadata: dict | None = None
):
    MessageBus.send(
        "EventSphere",
        "NotificationAgent",
        "INFORM",
        {
            "user_id": user_id,
            "message": message,
            "type": notification_type,
            **(metadata or {})
        }
    )

    notification_agent.process_inbox()


# -------------------------------------------------
# QR CODE GENERATION
# -------------------------------------------------

def generate_qr_base64(code: str):
    image = qrcode.make(code)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    return base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")


# -------------------------------------------------
# HOME AND HEALTH
# -------------------------------------------------

@app.get("/", include_in_schema=False)
def home():
    index_file = TEMPLATES_DIR / "index.html"

    if not index_file.exists():
        return {
            "application": "EventSphere",
            "message": "Frontend index.html has not been created yet.",
            "api_documentation": "/docs"
        }

    return FileResponse(index_file)


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "application": "EventSphere",
        "agents": [
            "VenueAgent",
            "BookingAgent",
            "TicketAgent",
            "WaitlistAgent",
            "NotificationAgent"
        ]
    }


# -------------------------------------------------
# AUTHENTICATION ROUTES
# -------------------------------------------------

@app.post("/api/auth/register")
def register(
    data: UserCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(
        User.email == data.email
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role="attendee"
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Registration could not be completed"
        )

    return {
        "message": "Registration successful",
        "user_id": user.id,
        "role": user.role
    }


@app.post(
    "/api/auth/login",
    response_model=TokenResponse
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(
        form_data.username,
        form_data.password,
        db
    )

    return create_user_token(user)


@app.post(
    "/api/auth/login-json",
    response_model=TokenResponse
)
def login_json(
    data: UserLogin,
    db: Session = Depends(get_db)
):
    user = authenticate_user(
        data.email,
        data.password,
        db
    )

    return create_user_token(user)


@app.get("/api/auth/me")
def current_profile(
    user: User = Depends(get_current_user)
):
    return {
        "id": user.id,
        "name": user.full_name,
        "email": user.email,
        "role": user.role
    }


# -------------------------------------------------
# VENUE MANAGEMENT
# -------------------------------------------------

@app.post("/api/admin/venues")
def create_venue(
    data: VenueCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    venue = Venue(**data.model_dump())

    try:
        db.add(venue)
        db.commit()
        db.refresh(venue)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Venue could not be created"
        )

    return {
        "message": "Venue created",
        "venue_id": venue.id
    }


@app.put("/api/admin/venues/{venue_id}")
def update_venue(
    venue_id: int,
    data: VenueCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    venue = db.query(Venue).filter(
        Venue.id == venue_id
    ).first()

    if not venue:
        raise HTTPException(404, "Venue not found")

    for field, value in data.model_dump().items():
        setattr(venue, field, value)

    try:
        db.commit()
        db.refresh(venue)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Venue could not be updated"
        )

    return {
        "message": "Venue updated successfully",
        "venue_id": venue.id
    }


@app.get("/api/venues")
def list_venues(
    db: Session = Depends(get_db)
):
    venues = db.query(Venue).order_by(
        Venue.name
    ).all()

    return [
        {
            "id": venue.id,
            "name": venue.name,
            "location": venue.location,
            "capacity": venue.capacity,
            "description": venue.description,
            "image": venue.image,
            "hourly_rate": venue.hourly_rate,
            "available_for_hire": venue.available_for_hire
        }
        for venue in venues
    ]


# -------------------------------------------------
# PRIVATE VENUE HIRE
# -------------------------------------------------

@app.post("/api/venue-hire")
def create_venue_hire_request(
    data: VenueHireCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("attendee"))
):
    start = data.start_time.replace(tzinfo=None)
    end = data.end_time.replace(tzinfo=None)

    if end <= start:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    venue = db.query(Venue).filter(
        Venue.id == data.venue_id
    ).first()

    if not venue:
        raise HTTPException(404, "Venue not found")

    if not venue.available_for_hire:
        raise HTTPException(
            status_code=400,
            detail="This venue is not available for private hire"
        )

    if data.guest_count > venue.capacity:
        raise HTTPException(
            status_code=400,
            detail="Guest count exceeds venue capacity"
        )

    result = deliver_message(
        venue_agent,
        "EventSphere",
        {
            "action": "check_hire",
            "venue_id": venue.id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "guest_count": data.guest_count
        }
    )

    performative = result.get("performative")
    content = result.get("content", {})

    if performative == "FAILURE":
        raise HTTPException(
            status_code=500,
            detail=content.get(
                "reason",
                "Venue agent failed"
            )
        )

    if performative == "AGREE":
        # Routine requests are automatically confirmed.
        request_status = "confirmed"
        quoted_price = content.get("quoted_price", 0)

    elif performative == "PROPOSE":
        request_status = "proposed"
        quoted_price = content.get("quoted_price", 0)

    else:
        request_status = "rejected"
        quoted_price = 0

    hire_request = VenueHireRequest(
        user_id=user.id,
        venue_id=venue.id,
        start_time=start,
        end_time=end,
        purpose=data.purpose,
        guest_count=data.guest_count,
        quoted_price=quoted_price,
        status=request_status
    )

    try:
        db.add(hire_request)
        db.commit()
        db.refresh(hire_request)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Venue hire request could not be saved"
        )

    if request_status == "confirmed":
        notification_message = (
            f"Your private hire request for {venue.name} "
            f"has been automatically confirmed. "
            f"Estimated price: {quoted_price}."
        )

    elif request_status == "proposed":
        notification_message = (
            f"Your requested slot at {venue.name} is unavailable. "
            "Alternative venues or dates have been suggested."
        )

    else:
        notification_message = (
            f"Your private hire request for {venue.name} "
            "could not be accepted."
        )

    notify_user(
        user.id,
        notification_message,
        "venue_hire"
    )

    return {
        "message": notification_message,
        "request_id": hire_request.id,
        "status": request_status,
        "quoted_price": quoted_price,
        "alternatives": content.get("alternatives", [])
    }


@app.get("/api/venue-hire/my-requests")
def my_venue_hire_requests(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("attendee"))
):
    requests = db.query(VenueHireRequest).filter(
        VenueHireRequest.user_id == user.id
    ).order_by(
        desc(VenueHireRequest.id)
    ).all()

    return [
        {
            "request_id": request.id,
            "venue_id": request.venue_id,
            "start_time": request.start_time.isoformat(),
            "end_time": request.end_time.isoformat(),
            "purpose": request.purpose,
            "guest_count": request.guest_count,
            "quoted_price": request.quoted_price,
            "status": request.status
        }
        for request in requests
    ]


@app.get("/api/admin/venue-hire-requests")
def admin_venue_hire_requests(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    requests = db.query(VenueHireRequest).order_by(
        desc(VenueHireRequest.id)
    ).all()

    return [
        {
            "request_id": request.id,
            "user_id": request.user_id,
            "venue_id": request.venue_id,
            "start_time": request.start_time.isoformat(),
            "end_time": request.end_time.isoformat(),
            "purpose": request.purpose,
            "guest_count": request.guest_count,
            "quoted_price": request.quoted_price,
            "status": request.status
        }
        for request in requests
    ]


@app.post(
    "/api/admin/venue-hire-requests/{request_id}/approve"
)
def approve_venue_hire_request(
    request_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    hire_request = db.query(VenueHireRequest).filter(
        VenueHireRequest.id == request_id
    ).with_for_update().first()

    if not hire_request:
        raise HTTPException(404, "Hire request not found")

    if hire_request.status not in ("pending", "proposed"):
        raise HTTPException(
            400,
            "Only pending or proposed requests can be approved"
        )

    result = deliver_message(
        venue_agent,
        "EventSphere",
        {
            "action": "check_hire",
            "venue_id": hire_request.venue_id,
            "start_time": hire_request.start_time.isoformat(),
            "end_time": hire_request.end_time.isoformat(),
            "guest_count": hire_request.guest_count,
            "hire_request_id": hire_request.id
        }
    )

    content = result.get("content", {})

    if result.get("performative") != "AGREE":
        raise HTTPException(
            status_code=409,
            detail={
                "reason": content.get(
                    "reason",
                    "The venue is no longer available"
                ),
                "alternatives": content.get("alternatives", [])
            }
        )

    hire_request.status = "confirmed"
    hire_request.quoted_price = content.get(
        "quoted_price",
        hire_request.quoted_price
    )

    try:
        db.commit()
        db.refresh(hire_request)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Hire request approval could not be saved"
        )

    notify_user(
        hire_request.user_id,
        f"Your private venue hire request {hire_request.id} has been approved.",
        "venue_hire_approved"
    )

    return {
        "message": "Venue hire request approved",
        "request_id": hire_request.id,
        "status": hire_request.status,
        "quoted_price": hire_request.quoted_price
    }


@app.post(
    "/api/admin/venue-hire-requests/{request_id}/reject"
)
def reject_venue_hire_request(
    request_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    hire_request = db.query(VenueHireRequest).filter(
        VenueHireRequest.id == request_id
    ).first()

    if not hire_request:
        raise HTTPException(404, "Hire request not found")

    if hire_request.status not in ("pending", "proposed"):
        raise HTTPException(
            400,
            "This request cannot be rejected in its current status"
        )

    hire_request.status = "rejected"

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Hire request rejection could not be saved"
        )

    notify_user(
        hire_request.user_id,
        f"Your private venue hire request {hire_request.id} has been rejected.",
        "venue_hire_rejected"
    )

    return {
        "message": "Venue hire request rejected",
        "request_id": hire_request.id,
        "status": hire_request.status
    }


# -------------------------------------------------
# EVENT MANAGEMENT
# -------------------------------------------------

@app.post("/api/admin/events")
def create_event(
    data: EventWithTicketsCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    venue = db.query(Venue).filter(
        Venue.id == data.venue_id
    ).first()

    if not venue:
        raise HTTPException(404, "Venue not found")

    start = data.start_time.replace(tzinfo=None)
    end = data.end_time.replace(tzinfo=None)

    if end <= start:
        raise HTTPException(
            status_code=400,
            detail="Event end time must be after start time"
        )

    if not data.ticket_categories:
        raise HTTPException(
            status_code=400,
            detail="At least one ticket category is required"
        )

    total_tickets = sum(
        category.quantity
        for category in data.ticket_categories
    )

    if total_tickets > venue.capacity:
        raise HTTPException(
            status_code=400,
            detail="Total tickets exceed venue capacity"
        )

    event = Event(
        title=data.title,
        category=data.category,
        venue_id=data.venue_id,
        start_time=start,
        end_time=end,
        description=data.description,
        status="draft"
    )

    try:
        db.add(event)
        db.flush()

        for category in data.ticket_categories:
            db.add(TicketCategory(
                event_id=event.id,
                name=category.name,
                price=category.price,
                quantity=category.quantity,
                sold=0
            ))

        db.commit()
        db.refresh(event)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Event could not be created"
        )

    return {
        "message": "Event saved as draft",
        "event_id": event.id,
        "total_tickets": total_tickets
    }


@app.get("/api/admin/events")
def admin_list_events(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    events = db.query(Event).order_by(
        desc(Event.id)
    ).all()

    result = []

    for event in events:
        venue = db.query(Venue).filter(
            Venue.id == event.venue_id
        ).first()

        categories = db.query(TicketCategory).filter(
            TicketCategory.event_id == event.id
        ).all()

        total_quantity = sum(
            category.quantity for category in categories
        )
        total_sold = sum(
            category.sold for category in categories
        )

        result.append({
            "id": event.id,
            "title": event.title,
            "category": event.category,
            "venue_id": event.venue_id,
            "venue_name": venue.name if venue else None,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "description": event.description,
            "status": event.status,
            "total_capacity": total_quantity,
            "tickets_sold": total_sold,
            "tickets_available": total_quantity - total_sold,
            "ticket_categories": [
                {
                    "id": category.id,
                    "name": category.name,
                    "price": category.price,
                    "quantity": category.quantity,
                    "sold": category.sold,
                    "available": category.quantity - category.sold
                }
                for category in categories
            ]
        })

    return result


@app.post("/api/admin/events/{event_id}/publish")
def publish_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    event = db.query(Event).filter(
        Event.id == event_id
    ).first()

    if not event:
        raise HTTPException(404, "Event not found")

    if event.status == "cancelled":
        raise HTTPException(
            400,
            "Cancelled events cannot be published"
        )

    if event.status == "published":
        raise HTTPException(
            400,
            "Event is already published"
        )

    categories = db.query(TicketCategory).filter(
        TicketCategory.event_id == event_id
    ).all()

    if not categories:
        raise HTTPException(
            400,
            "Add ticket categories first"
        )

    venue = db.query(Venue).filter(
        Venue.id == event.venue_id
    ).first()

    if not venue:
        raise HTTPException(404, "Event venue not found")

    total_tickets = sum(
        category.quantity for category in categories
    )

    if total_tickets > venue.capacity:
        raise HTTPException(
            400,
            "Ticket allocation exceeds venue capacity"
        )

    result = deliver_message(
        venue_agent,
        "EventSphere",
        {
            "action": "check_event_slot",
            "event_id": event.id,
            "venue_id": event.venue_id,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "total_tickets": total_tickets
        }
    )

    if result.get("performative") != "AGREE":
        reason = result.get("content", {}).get(
            "reason",
            "Venue unavailable"
        )

        raise HTTPException(
            status_code=409,
            detail=reason
        )

    event.status = "published"

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Event could not be published"
        )

    return {
        "message": "Event published successfully",
        "event_id": event.id,
        "status": event.status
    }


@app.get("/api/events")
def browse_events(
    keyword: str = "",
    category: str = "",
    db: Session = Depends(get_db)
):
    query = db.query(Event).filter(
        Event.status == "published"
    )

    if keyword.strip():
        query = query.filter(
            Event.title.ilike(f"%{keyword.strip()}%")
        )

    if category.strip():
        query = query.filter(
            Event.category.ilike(category.strip())
        )

    events = query.order_by(Event.start_time).all()

    result = []

    for event in events:
        venue = db.query(Venue).filter(
            Venue.id == event.venue_id
        ).first()

        categories = db.query(TicketCategory).filter(
            TicketCategory.event_id == event.id
        ).all()

        result.append({
            "id": event.id,
            "title": event.title,
            "category": event.category,
            "venue_id": event.venue_id,
            "venue_name": venue.name if venue else None,
            "venue_location": venue.location if venue else None,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "description": event.description,
            "tickets": [
                {
                    "id": category.id,
                    "name": category.name,
                    "price": category.price,
                    "quantity": category.quantity,
                    "sold": category.sold,
                    "available": category.quantity - category.sold
                }
                for category in categories
            ]
        })

    return result


@app.post("/api/admin/events/{event_id}/cancel")
def cancel_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    event = db.query(Event).filter(
        Event.id == event_id
    ).first()

    if not event:
        raise HTTPException(404, "Event not found")

    if event.status == "cancelled":
        raise HTTPException(
            400,
            "Event is already cancelled"
        )

    event.status = "cancelled"

    bookings = db.query(Booking).filter(
        Booking.event_id == event_id,
        Booking.status == "confirmed"
    ).all()

    try:
        for booking in bookings:
            booking.status = "cancelled"

            tickets = db.query(Ticket).filter(
                Ticket.booking_id == booking.id
            ).all()

            for ticket in tickets:
                ticket.status = "cancelled"

            notify_user(
                booking.user_id,
                f"Event {event.title} was cancelled. "
                f"Your full simulated refund is {booking.total_amount}.",
                "event_cancelled"
            )

        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Event cancellation could not be completed"
        )

    return {
        "message": "Event cancelled. Confirmed bookings were cancelled and full simulated refunds were issued.",
        "cancelled_bookings": len(bookings)
    }


# -------------------------------------------------
# BOOKING
# -------------------------------------------------

@app.post("/api/bookings")
def book_tickets(
    data: BookingCreate,
    user: User = Depends(require_role("attendee"))
):
    content = {
        "action": "book_tickets",
        "user_id": user.id,
        "event_id": data.event_id,
        "category_id": data.category_id,
        "quantity": data.quantity
    }

    result = deliver_message(
        booking_agent,
        "EventSphere",
        content
    )

    if result.get("performative") != "AGREE":
        reason = result.get("content", {}).get(
            "reason",
            "Booking rejected"
        )

        # A single-ticket booking that loses the last available seat is
        # automatically placed at the end of the FIFO waitlist.
        if reason == "Not enough tickets available" and data.quantity == 1:
            waitlist_result = deliver_message(
                waitlist_agent,
                "BookingAgent",
                {
                    "action": "join_waitlist",
                    "user_id": user.id,
                    "event_id": data.event_id,
                    "category_id": data.category_id
                }
            )

            if waitlist_result.get("performative") == "AGREE":
                notification_agent.process_inbox()
                details = waitlist_result.get("content", {})
                return {
                    "status": details.get("status", "waiting"),
                    "message": details.get(
                        "message",
                        "All tickets are sold. You have been added to the waiting list."
                    ),
                    "waitlist_id": details.get("waitlist_id"),
                    "queue_position": details.get("queue_position")
                }

            reason = waitlist_result.get("content", {}).get(
                "reason",
                reason
            )

        raise HTTPException(status_code=400, detail=reason)

    booking_id = result["content"]["booking_id"]

    ticket_result = deliver_message(
        ticket_agent,
        "BookingAgent",
        {
            "action": "issue_tickets",
            "booking_id": booking_id
        }
    )

    if ticket_result.get("performative") != "INFORM":
        # Do not report a successful ticket booking when ticket
        # issuance has failed. The administrator can inspect the
        # booking and agent message log for recovery.
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Booking was created, but ticket issuance failed.",
                "booking_id": booking_id,
                "reason": ticket_result.get("content", {}).get(
                    "reason",
                    "Ticket issuance failed"
                )
            }
        )

    ticket_codes = ticket_result.get(
        "content", {}
    ).get("tickets", [])

    notify_user(
        user.id,
        f"Your booking {booking_id} is confirmed.",
        "booking_confirmed"
    )

    return {
        "message": "Booking successful",
        "booking": result["content"],
        "tickets": ticket_codes,
        "qr_codes": [
            generate_qr_base64(code)
            for code in ticket_codes
        ]
    }


@app.get("/api/bookings/history")
def booking_history(
    user: User = Depends(require_role("attendee")),
    db: Session = Depends(get_db)
):
    bookings = db.query(Booking).filter(
        Booking.user_id == user.id
    ).order_by(
        desc(Booking.id)
    ).all()

    result = []

    for booking in bookings:
        event = db.query(Event).filter(
            Event.id == booking.event_id
        ).first()

        tickets = db.query(Ticket).filter(
            Ticket.booking_id == booking.id
        ).all()

        result.append({
            "booking_id": booking.id,
            "event_id": booking.event_id,
            "event_title": event.title if event else None,
            "quantity": booking.quantity,
            "total_amount": booking.total_amount,
            "payment_reference": booking.payment_reference,
            "status": booking.status,
            "created_at": booking.created_at.isoformat(),
            "tickets": [
                {
                    "id": ticket.id,
                    "qr_code": ticket.qr_code,
                    "status": ticket.status,
                    "checked_in": ticket.checked_in
                }
                for ticket in tickets
            ]
        })

    return result


@app.post("/api/bookings/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    user: User = Depends(require_role("attendee"))
):
    result = deliver_message(
        booking_agent,
        "EventSphere",
        {
            "action": "cancel_booking",
            "booking_id": booking_id,
            "user_id": user.id
        }
    )

    if result.get("performative") != "AGREE":
        raise HTTPException(
            status_code=400,
            detail=result.get("content", {}).get(
                "reason",
                "Cancellation failed"
            )
        )

    notify_user(
        user.id,
        f"Booking {booking_id} was cancelled. "
        f"Refund: {result['content'].get('refund_amount', 0)}",
        "booking_cancelled"
    )

    # Return the released ticket(s) to the FIFO waitlist immediately.
    category_id = result["content"].get("category_id")
    released_offers = []
    if category_id:
        released_offers = waitlist_agent.offer_available(category_id)
        notification_agent.process_inbox()

    response = dict(result["content"])
    response["waitlist_offers_created"] = len(released_offers)
    return response


# -------------------------------------------------
# TICKET CHECK-IN
# -------------------------------------------------

@app.post("/api/staff/scan")
def scan_ticket(
    data: CheckInRequest,
    user: User = Depends(require_role("staff", "admin"))
):
    result = deliver_message(
        ticket_agent,
        "EventSphere",
        {
            "action": "scan_ticket",
            "code": data.code,
            "event_id": data.event_id
        }
    )

    if result.get("performative") != "AGREE":
        raise HTTPException(
            status_code=400,
            detail=result.get("content", {}).get(
                "reason",
                "Ticket rejected"
            )
        )

    return result["content"]


# -------------------------------------------------
# WAITLIST
# -------------------------------------------------

@app.post("/api/waitlist")
def join_waitlist(
    data: WaitlistRequest,
    user: User = Depends(require_role("attendee"))
):
    result = deliver_message(
        waitlist_agent,
        "EventSphere",
        {
            "action": "join_waitlist",
            "user_id": user.id,
            "event_id": data.event_id,
            "category_id": data.category_id
        }
    )

    if result.get("performative") != "AGREE":
        raise HTTPException(
            status_code=400,
            detail=result.get("content", {}).get(
                "reason",
                "Waitlist request failed"
            )
        )

    notification_agent.process_inbox()
    return result["content"]


@app.get("/api/waitlist/my-entries")
def my_waitlist_entries(
    user: User = Depends(require_role("attendee")),
    db: Session = Depends(get_db)
):
    entries = db.query(WaitlistEntry).filter(
        WaitlistEntry.user_id == user.id
    ).order_by(WaitlistEntry.id.asc()).all()

    result = []
    for entry in entries:
        position = None
        if entry.status == "waiting":
            position = db.query(WaitlistEntry).filter(
                WaitlistEntry.category_id == entry.category_id,
                WaitlistEntry.status == "waiting",
                WaitlistEntry.id <= entry.id
            ).count()

        result.append({
            "waitlist_id": entry.id,
            "event_id": entry.event_id,
            "category_id": entry.category_id,
            "status": entry.status,
            "queue_position": position,
            "hold_expires_at": (
                entry.hold_expires_at.isoformat()
                if entry.hold_expires_at else None
            )
        })

    return result


@app.post("/api/waitlist/{waitlist_id}/claim")
def claim_waitlist_offer(
    waitlist_id: int,
    user: User = Depends(require_role("attendee"))
):
    result = deliver_message(
        booking_agent,
        "WaitlistAgent",
        {
            "action": "claim_waitlist_offer",
            "waitlist_id": waitlist_id,
            "user_id": user.id
        }
    )

    if result.get("performative") != "AGREE":
        raise HTTPException(
            status_code=400,
            detail=result.get("content", {}).get(
                "reason",
                "Waitlist offer could not be claimed"
            )
        )

    booking_details = result["content"]
    ticket_result = deliver_message(
        ticket_agent,
        "BookingAgent",
        {
            "action": "issue_tickets",
            "booking_id": booking_details["booking_id"]
        }
    )

    if ticket_result.get("performative") != "INFORM":
        raise HTTPException(
            status_code=500,
            detail={
                "message": "The offer was claimed, but ticket issuance failed.",
                "booking_id": booking_details["booking_id"],
                "reason": ticket_result.get("content", {}).get(
                    "reason",
                    "Ticket issuance failed"
                )
            }
        )

    ticket_codes = ticket_result.get("content", {}).get("tickets", [])
    notify_user(
        user.id,
        f"Your waitlist offer was claimed. Booking {booking_details['booking_id']} is confirmed.",
        "waitlist_claimed",
        {"waitlist_id": waitlist_id}
    )

    return {
        "message": "Waitlist offer claimed. Your ticket is confirmed.",
        "booking": booking_details,
        "tickets": ticket_codes,
        "qr_codes": [
            generate_qr_base64(code)
            for code in ticket_codes
        ]
    }


# -------------------------------------------------
# NOTIFICATIONS
# -------------------------------------------------

@app.get("/api/notifications")
def user_notifications(
    user: User = Depends(require_role("attendee"))
):
    return notification_agent.get_notifications(user.id)


# -------------------------------------------------
# ADMIN DASHBOARD
# -------------------------------------------------

@app.get("/api/admin/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    total_events = db.query(Event).filter(
        Event.status == "published"
    ).count()

    total_venues = db.query(Venue).count()

    total_bookings = db.query(Booking).filter(
        Booking.status == "confirmed"
    ).count()

    total_tickets_sold = db.query(
        func.coalesce(func.sum(Booking.quantity), 0)
    ).filter(
        Booking.status == "confirmed"
    ).scalar()

    simulated_revenue = db.query(
        func.coalesce(func.sum(Booking.total_amount), 0)
    ).filter(
        Booking.status == "confirmed"
    ).scalar()

    total_checkins = db.query(Ticket).filter(
        Ticket.checked_in.is_(True)
    ).count()

    event_summary = []

    events = db.query(Event).order_by(
        desc(Event.id)
    ).all()

    for event in events:
        categories = db.query(TicketCategory).filter(
            TicketCategory.event_id == event.id
        ).all()

        capacity = sum(
            category.quantity for category in categories
        )

        sold = sum(
            category.sold for category in categories
        )

        checked_in = db.query(Ticket).filter(
            Ticket.event_id == event.id,
            Ticket.checked_in.is_(True)
        ).count()

        event_summary.append({
            "event_id": event.id,
            "title": event.title,
            "status": event.status,
            "capacity": capacity,
            "tickets_sold": sold,
            "tickets_available": max(capacity - sold, 0),
            "checked_in": checked_in
        })

    return {
        "total_published_events": total_events,
        "total_venues": total_venues,
        "confirmed_bookings": total_bookings,
        "tickets_sold": int(total_tickets_sold or 0),
        "simulated_revenue": float(simulated_revenue or 0),
        "total_checkins": total_checkins,
        "events": event_summary
    }


# -------------------------------------------------
# ADMIN AGENT MESSAGE LOG
# -------------------------------------------------

@app.get("/api/admin/agent-messages")
def agent_messages(
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    messages = db.query(AgentMessage).order_by(
        desc(AgentMessage.id)
    ).limit(200).all()

    return [
        {
            "sender": message.sender,
            "receiver": message.receiver,
            "performative": message.performative,
            "content": message.content,
            "conversation_id": message.conversation_id,
            "created_at": message.created_at.isoformat()
        }
        for message in messages
    ]
