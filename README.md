# EventSphere – Intelligent Venue Booking & Digital Ticketing Platform

<p align="center">

  **🚀 LIVE WEBSITE**

  ### 🌐 [https://two021ict87-eventsphere.onrender.com](https://two021ict87-eventsphere.onrender.com)

  **Explore EventSphere online!**

  [GitHub Repository](https://github.com/KeshanyaRamesh/2021ict87_EventSphere_AgentBasedComputing) · [API Documentation (Swagger)](https://two021ict87-eventsphere.onrender.com/docs)

</p>

---

## 📌 Project Overview

EventSphere is a mobile-friendly university event management, venue booking, and digital ticketing platform developed for the **IT4123 – Agent Based Computing Practical (ICA 02)** at the University of Vavuniya.

The platform uses five cooperating intelligent software agents to coordinate venue scheduling, ticket bookings, QR-based ticket validation, waitlist management, and notifications.

**🔗 Live Deployment:** https://two021ict87-eventsphere.onrender.com

**📖 API Documentation:** https://two021ict87-eventsphere.onrender.com/docs

## ✨ Main Features

- User registration and secure login.
- JWT authentication and password hashing.
- Role-based access for administrators, staff, and attendees.
- Venue creation and management.
- Event creation, publishing, and management.
- Event browsing, searching, and category filtering.
- Ticket categories and multi-ticket booking.
- Ticket inventory validation and simulated payments.
- QR code ticket generation.
- Staff QR scanner and manual ticket validation.
- Duplicate, invalid, cancelled, and incorrect-event ticket rejection.
- Private venue-hire requests and price calculation.
- Venue conflict detection and alternative suggestions.
- Automatic first-come, first-served (FCFS) waitlisting when a single-ticket booking finds the category sold out.
- Waitlist position is based on the database-generated entry ID (oldest entry first).
- When a confirmed booking is cancelled, the released ticket is offered to the earliest waiting attendee.
- Waitlist offers reserve a ticket for 10 minutes; the attendee can claim the offer to confirm the booking and receive a QR ticket.
- Expired or unclaimed offers are passed to the next waiting attendee.
- Attendee notifications.
- Booking history, cancellation, and refund calculation.
- Administrative dashboard and agent communication logs.

## 🤖 Multi-Agent Architecture

EventSphere consists of five cooperating agents:

| Agent | Responsibility |
|---|---|
| VenueAgent | Checks venue availability, capacity, and scheduling conflicts. |
| BookingAgent | Processes booking requests and manages ticket inventory. |
| TicketAgent | Generates and validates digital tickets. |
| WaitlistAgent | Maintains FIFO waitlist order, offers released tickets, and advances expired offers. |
| NotificationAgent | Handles and stores user notifications. |

### First-Come, First-Served Waitlist Flow

1. The BookingAgent atomically checks and updates the ticket-category inventory.
2. If a single-ticket booking finds no inventory, the API automatically asks the WaitlistAgent to add the attendee to the queue.
3. The WaitlistAgent orders waiting entries by ascending database ID, preserving the order in which entries were accepted.
4. When a confirmed booking is cancelled, the released inventory is offered to the oldest waiting attendee(s).
5. Each offer holds one ticket for 10 minutes. The attendee claims it through the notification shown in the website.
6. The BookingAgent validates the offer, marks it as claimed only once, and atomically allocates the ticket. The TicketAgent then issues the QR code.
7. If the offer expires, the WaitlistAgent offers the ticket to the next waiting attendee.

**Current limitation:** each waitlist entry represents one ticket. The automatic waitlist path is for a one-ticket booking request; multi-ticket requests are not split into separate queue entries.

### Agent Communication

Agents communicate using structured JSON messages.

Supported performatives:

`REQUEST` · `AGREE` · `REFUSE` · `PROPOSE` · `INFORM` · `FAILURE`

Messages contain:

- Sender
- Receiver
- Performative
- Content
- Conversation ID

Agent messages are persisted for monitoring through the administrative interface.

## 🛠️ Technology Stack

**Backend**
- Python
- FastAPI
- SQLAlchemy
- Pydantic
- JWT Authentication

**Frontend**
- HTML
- CSS
- JavaScript

**Database**
- SQLite for local development
- PostgreSQL for hosted deployment

**Additional Technologies**
- QR Code Generation
- Pytest
- Uvicorn
- Render Cloud Deployment

## 📂 Project Structure

```text
EventSphere/
│
├── app/
│   ├── agents/
│   │   ├── base.py
│   │   ├── booking_agent.py
│   │   ├── notification_agent.py
│   │   ├── ticket_agent.py
│   │   ├── venue_agent.py
│   │   └── waitlist_agent.py
│   │
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── security.py
│   └── seed_demo.py
│
├── static/
├── templates/
├── tests/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt