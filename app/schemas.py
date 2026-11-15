
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VenueCreate(BaseModel):
    name: str
    location: str
    capacity: int = Field(gt=0)
    description: Optional[str] = None
    image: Optional[str] = None
    hourly_rate: float = Field(ge=0)
    available_for_hire: bool = True


class EventCreate(BaseModel):
    title: str
    category: str
    venue_id: int
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None


class TicketCategoryCreate(BaseModel):
    name: str
    price: float = Field(ge=0)
    quantity: int = Field(gt=0)


class BookingCreate(BaseModel):
    event_id: int
    category_id: int
    quantity: int = Field(gt=0, le=6)


class VenueHireCreate(BaseModel):
    venue_id: int
    start_time: datetime
    end_time: datetime
    purpose: str
    guest_count: int = Field(gt=0)


class AgentMessageSchema(BaseModel):
    sender: str
    receiver: str
    performative: str
    content: dict
    conversation_id: str



class EventWithTicketsCreate(EventCreate):
    ticket_categories: list[TicketCategoryCreate]


class EventStatusUpdate(BaseModel):
    status: str


class CheckInRequest(BaseModel):
    code: str
    event_id: int


class WaitlistRequest(BaseModel):
    event_id: int
    category_id: int
