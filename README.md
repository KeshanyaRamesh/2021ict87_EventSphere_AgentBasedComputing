# EventSphere â€“ Intelligent Venue Booking and Digital Ticketing Platform

**Module:** IT4123 â€“ Agent Based Computing Practical
**Assessment:** ICA 02
**Institution:** University of Vavuniya

## 1. Project Overview

EventSphere is a mobile-friendly venue booking and digital ticketing platform developed for the IT4123 Agent Based Computing Practical ICA 02.

The platform uses five cooperating software agents to manage venue availability, event bookings, digital tickets, waitlists, and notifications.

## 2. Main Features

- Attendee registration and login.
- Secure password hashing and JWT authentication.
- Role-based access for administrators, staff, and attendees.
- Venue creation and management.
- Event creation, publishing, and management.
- Event browsing and ticket-category selection.
- Multi-ticket booking and inventory validation.
- Digital QR ticket generation.
- Staff QR/manual ticket validation.
- Duplicate and invalid ticket rejection.
- Private venue hire requests and price calculation.
- Venue conflict checking and alternative suggestions.
- Waitlist management and expiry processing.
- User notifications.
- Administrative dashboard and agent message logs.

## 3. Multi-Agent Architecture

EventSphere contains five agents:

| Agent | Responsibility |
|---|---|
| VenueAgent | Checks venue availability, capacity, and scheduling conflicts. |
| BookingAgent | Processes booking requests and manages ticket inventory. |
| TicketAgent | Issues and validates digital tickets. |
| WaitlistAgent | Manages waitlist entries and expiry processing. |
| NotificationAgent | Stores and manages user notifications. |

Agents communicate through structured JSON messages.

Supported performatives:

`REQUEST`, `AGREE`, `REFUSE`, `PROPOSE`, `INFORM`, `FAILURE`.

Messages include sender, receiver, performative, content, and conversation ID. Agent messages are persisted for monitoring.

## 4. Technology Stack

**Backend**
- Python
- FastAPI
- SQLAlchemy
- Pydantic
- SQLite
- JWT authentication

**Frontend**
- HTML
- CSS
- JavaScript

**Additional technologies**
- QR code generation
- Pytest
- Uvicorn

## 5. Project Structure

```text
EventSphere/
â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ agents/
â”‚   â”‚   â”œâ”€â”€ base.py
â”‚   â”‚   â”œâ”€â”€ booking_agent.py
â”‚   â”‚   â”œâ”€â”€ notification_agent.py
â”‚   â”‚   â”œâ”€â”€ ticket_agent.py
â”‚   â”‚   â”œâ”€â”€ venue_agent.py
â”‚   â”‚   â””â”€â”€ waitlist_agent.py
â”‚   â”œâ”€â”€ database.py
â”‚   â”œâ”€â”€ main.py
â”‚   â”œâ”€â”€ models.py
â”‚   â”œâ”€â”€ schemas.py
â”‚   â”œâ”€â”€ security.py
â”‚   â””â”€â”€ seed_demo.py
â”œâ”€â”€ reports/
â”œâ”€â”€ static/
â”œâ”€â”€ templates/
â”œâ”€â”€ tests/
â”œâ”€â”€ .env.example
â”œâ”€â”€ .gitignore
â”œâ”€â”€ README.md
â””â”€â”€ requirements.txt
```

## 6. Installation and Setup

### Prerequisites

- Python 3.10 or later.
- pip.

### Step 1: Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd EventSphere
```

### Step 2: Create a virtual environment

```bash
python -m venv venv
```

### Step 3: Activate the virtual environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 4: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Configure environment variables

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Set a strong, unique `SECRET_KEY` in `.env` before deployment.

The default database configuration uses SQLite:

```text
DATABASE_URL=sqlite:///./eventsphere.db
```

Do not commit `.env` or expose its contents.

### Step 6: Start the application

```bash
python -m uvicorn app.main:app --reload
```

Open:

- Application: http://127.0.0.1:8000
- Swagger API documentation: http://127.0.0.1:8000/docs

## 7. Running Tests

Run the automated test suite:

```bash
python -m pytest -q
```

Latest local test result:

- 17 tests passed.
- 0 test failures.

The tests cover agent messaging, booking inventory, venue availability, ticket validation, waitlist handling, and notifications.

## 8. Security

- Password hashing.
- JWT-based authentication.
- Role-based access control.
- Environment-based configuration.
- `.env` and local database files excluded from Git.

Use a strong secret key and HTTPS for deployment.

## 9. Project Links

**GitHub Repository:** To be added.
**Live Application:** To be added after deployment.

## 10. Assessment Information

Developed for IT4123 â€“ Agent Based Computing Practical, ICA 02, University of Vavuniya.