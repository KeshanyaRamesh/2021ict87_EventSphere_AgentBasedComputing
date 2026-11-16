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
- Waitlist registration and expiry processing.
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
| WaitlistAgent | Manages waitlist entries and expired offers. |
| NotificationAgent | Handles and stores user notifications. |

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
```

## 🚀 Run Locally

### Prerequisites

- Python 3.11 or later
- pip
- Git

### Step 1 – Clone the repository

```bash
git clone https://github.com/KeshanyaRamesh/2021ict87_EventSphere_AgentBasedComputing.git
```

### Step 2 – Navigate into the project

```bash
cd 2021ict87_EventSphere_AgentBasedComputing
```

### Step 3 – Create a virtual environment

```bash
python -m venv venv
```

### Step 4 – Activate the virtual environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 5 – Install dependencies

```bash
pip install -r requirements.txt
```

### Step 6 – Configure environment variables

```powershell
Copy-Item .env.example .env
```

Update the `.env` file with a strong, unique secret key.

Example local configuration:

```env
DATABASE_URL=sqlite:///./eventsphere.db
SECRET_KEY=your-strong-secret-key
```

### Step 7 – Run the application

```bash
python -m uvicorn app.main:app --reload
```

### Step 8 – Open EventSphere

| Service | URL |
|---|---|
| Local Website | http://127.0.0.1:8000 |
| Local Swagger API | http://127.0.0.1:8000/docs |
| Live Website | https://two021ict87-eventsphere.onrender.com |
| Live Swagger API | https://two021ict87-eventsphere.onrender.com/docs |

## 🧪 Testing

Run the automated test suite:

```bash
python -m pytest -q
```

The recorded development test result was **17 passed**.

Tests cover agent messaging, booking inventory rules, venue availability, ticket validation, waitlist behaviour, and notification persistence.

## ☁️ Deployment

EventSphere is deployed as a cloud-hosted web service using **Render**.

- **Platform:** Render
- **Application:** FastAPI Web Service
- **Database:** Hosted PostgreSQL
- **Deployment URL:** https://two021ict87-eventsphere.onrender.com
- **API Documentation:** https://two021ict87-eventsphere.onrender.com/docs

## 🎓 Academic Information

| Detail | Information |
|---|---|
| Module | IT4123 – Agent Based Computing Practical |
| Assessment | ICA 02 |
| Institution | University of Vavuniya |
| Registration Number | 2021/ICT/87 |
| Student | Keshanya Ramesh |

## 👩‍💻 Author

**Keshanya Ramesh**

BSc (Hons) Information Technology  
University of Vavuniya

GitHub: [@KeshanyaRamesh](https://github.com/KeshanyaRamesh)

---

<p align="center">

  **EventSphere – Every Event Has a Place Here.**

  🌐 [Visit the Live Website](https://two021ict87-eventsphere.onrender.com)

</p>
