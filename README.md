# EventSphere - Intelligent Venue Booking and Digital Ticketing Platform

**Module:** IT4123 - Agent Based Computing Practical  
**Assessment:** ICA 02  
**Institution:** University of Vavuniya  
**Registration Number:** 2021/ICT/87


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
- Simulated payment processing and payment references.
- Digital QR ticket generation.
- Staff QR and manual ticket validation.
- Duplicate, invalid, cancelled, and incorrect-event ticket rejection.
- Private venue hire requests and price calculation.
- Venue conflict checking and alternative suggestions.
- Waitlist management and expiry processing.
- User notifications.
- Administrative dashboard and agent message logs.
- Booking history, cancellation, and refund calculation.

## 3. Multi-Agent Architecture

EventSphere contains five cooperating agents:

| Agent | Responsibility |
|---|---|
| VenueAgent | Checks venue availability, capacity, and scheduling conflicts. |
| BookingAgent | Processes booking requests and manages ticket inventory. |
| TicketAgent | Issues and validates digital tickets. |
| WaitlistAgent | Manages waitlist entries and expiry processing. |
| NotificationAgent | Stores and manages user notifications. |

Agents communicate through structured JSON messages.

Supported performatives:

`REQUEST`, `AGREE`, `REFUSE`, `PROPOSE`, `INFORM`, `FAILURE`

Messages include:
- Sender
- Receiver
- Performative
- Content
- Conversation ID

Agent messages are persisted for monitoring and can be viewed through the administrative interface.

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

**Additional Technologies**
- QR code generation
- Pytest
- Uvicorn

## 5. Project Structure

```text
EventSphere/
|
|-- app/
|   |-- agents/
|   |   |-- base.py
|   |   |-- booking_agent.py
|   |   |-- notification_agent.py
|   |   |-- ticket_agent.py
|   |   |-- venue_agent.py
|   |   |-- waitlist_agent.py
|   |
|   |-- database.py
|   |-- main.py
|   |-- models.py
|   |-- schemas.py
|   |-- security.py
|   |-- seed_demo.py
|
|-- reports/
|-- static/
|-- templates/
|-- tests/
|-- .env.example
|-- .gitignore
|-- README.md
|-- requirements.txt
```

## 6. Installation and Setup

### Prerequisites

- Python 3.11 or later.
- pip.
- Git.

### Step 1: Clone the repository

```bash
git clone https://github.com/KeshanyaRamesh/2021ict87_EventSphere_AgentBasedComputing.git
```

Navigate into the project directory:

```bash
cd 2021ict87_EventSphere_AgentBasedComputing
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

Create a `.env` file using the example configuration:

```powershell
Copy-Item .env.example .env
```

Update the `SECRET_KEY` in `.env` with a strong, unique secret key.

Default SQLite configuration:

```env
DATABASE_URL=sqlite:///./eventsphere.db
SECRET_KEY=replace-this-with-a-long-random-secret-before-deployment