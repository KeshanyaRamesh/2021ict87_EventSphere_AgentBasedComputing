
from datetime import datetime, timedelta

from app.agents.base import BaseAgent
from app.database import SessionLocal
from app.models import Venue, Event, VenueHireRequest


class VenueAgent(BaseAgent):

    def __init__(self):
        super().__init__("VenueAgent")
        self.turnaround_minutes = 30

    def is_available(
        self,
        db,
        venue_id,
        start_time,
        end_time,
        exclude_event_id=None,
        exclude_hire_request_id=None
    ):
        buffer = timedelta(minutes=self.turnaround_minutes)

        check_start = start_time - buffer
        check_end = end_time + buffer

        event_query = db.query(Event).filter(
            Event.venue_id == venue_id,
            Event.status != "cancelled",
            Event.start_time < check_end,
            Event.end_time > check_start
        )

        if exclude_event_id is not None:
            event_query = event_query.filter(
                Event.id != exclude_event_id
            )

        hire_query = db.query(VenueHireRequest).filter(
            VenueHireRequest.venue_id == venue_id,
            VenueHireRequest.status.in_(["pending", "confirmed"]),
            VenueHireRequest.start_time < check_end,
            VenueHireRequest.end_time > check_start
        )

        if exclude_hire_request_id is not None:
            hire_query = hire_query.filter(
                VenueHireRequest.id != exclude_hire_request_id
            )

        return (
            event_query.first() is None
            and hire_query.first() is None
        )

    def find_alternatives(
        self,
        db,
        venue,
        start,
        end,
        guests
    ):
        alternatives = []
        duration = end - start

        # Suggest the same venue on the next three days.
        for day in range(1, 4):

            alternative_start = start + timedelta(days=day)
            alternative_end = alternative_start + duration

            if self.is_available(
                db,
                venue.id,
                alternative_start,
                alternative_end
            ):
                alternatives.append({
                    "venue_id": venue.id,
                    "venue_name": venue.name,
                    "start_time": alternative_start.isoformat(),
                    "end_time": alternative_end.isoformat()
                })

        # Suggest other suitable venues at the requested time.
        other_venues = db.query(Venue).filter(
            Venue.id != venue.id,
            Venue.available_for_hire.is_(True),
            Venue.capacity >= guests
        ).all()

        for other in other_venues:

            if self.is_available(
                db,
                other.id,
                start,
                end
            ):
                alternatives.append({
                    "venue_id": other.id,
                    "venue_name": other.name,
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat()
                })

        return alternatives[:6]

    def process_message(self, message):

        content = message.get("content", {})
        action = content.get("action")
        conversation_id = message.get("conversation_id")

        db = SessionLocal()

        try:

            if action not in (
                "check_event_slot",
                "check_hire"
            ):
                return self.send_message(
                    message["sender"],
                    "FAILURE",
                    {"reason": "Unknown VenueAgent action"},
                    conversation_id
                )

            venue = db.query(Venue).filter(
                Venue.id == content.get("venue_id")
            ).first()

            if not venue:
                return self.send_message(
                    message["sender"],
                    "REFUSE",
                    {"reason": "Venue does not exist"},
                    conversation_id
                )

            try:
                start = datetime.fromisoformat(
                    content["start_time"]
                )
                end = datetime.fromisoformat(
                    content["end_time"]
                )
            except (KeyError, TypeError, ValueError):
                return self.send_message(
                    message["sender"],
                    "REFUSE",
                    {"reason": "Invalid date or time format"},
                    conversation_id
                )

            # Database currently stores naive local datetimes.
            start = start.replace(tzinfo=None)
            end = end.replace(tzinfo=None)

            if end <= start:
                return self.send_message(
                    message["sender"],
                    "REFUSE",
                    {"reason": "End time must be after start time"},
                    conversation_id
                )

            if action == "check_hire":

                if not venue.available_for_hire:
                    return self.send_message(
                        message["sender"],
                        "REFUSE",
                        {"reason": "Venue is not open for private hire"},
                        conversation_id
                    )

                guests = content.get("guest_count", 0)

                if (
                    isinstance(guests, bool)
                    or not isinstance(guests, int)
                    or guests <= 0
                ):
                    return self.send_message(
                        message["sender"],
                        "REFUSE",
                        {"reason": "Guest count must be a positive integer"},
                        conversation_id
                    )

                if guests > venue.capacity:
                    return self.send_message(
                        message["sender"],
                        "REFUSE",
                        {"reason": "Guest count exceeds venue capacity"},
                        conversation_id
                    )

                if venue.hourly_rate is None or venue.hourly_rate < 0:
                    return self.send_message(
                        message["sender"],
                        "FAILURE",
                        {"reason": "Venue hourly rate is invalid"},
                        conversation_id
                    )

            if action == "check_event_slot":

                total_tickets = content.get("total_tickets", 0)

                if (
                    isinstance(total_tickets, bool)
                    or not isinstance(total_tickets, int)
                    or total_tickets < 0
                ):
                    return self.send_message(
                        message["sender"],
                        "REFUSE",
                        {"reason": "Ticket quantity must be a non-negative integer"},
                        conversation_id
                    )

                if total_tickets > venue.capacity:
                    return self.send_message(
                        message["sender"],
                        "REFUSE",
                        {"reason": "Ticket quantity exceeds venue capacity"},
                        conversation_id
                    )

            exclude_event_id = (
                content.get("event_id")
                if action == "check_event_slot"
                else None
            )

            exclude_hire_id = (
                content.get("hire_request_id")
                if action == "check_hire"
                else None
            )

            available = self.is_available(
                db,
                venue.id,
                start,
                end,
                exclude_event_id=exclude_event_id,
                exclude_hire_request_id=exclude_hire_id
            )

            if available:

                if action == "check_hire":

                    hours = (
                        end - start
                    ).total_seconds() / 3600

                    price = round(
                        hours * venue.hourly_rate,
                        2
                    )

                    return self.send_message(
                        message["sender"],
                        "AGREE",
                        {
                            "reason": "Venue is available",
                            "venue_id": venue.id,
                            "quoted_price": price,
                            "duration_hours": round(hours, 2)
                        },
                        conversation_id
                    )

                return self.send_message(
                    message["sender"],
                    "AGREE",
                    {
                        "reason": "Venue time slot is available"
                    },
                    conversation_id
                )

            alternatives = []

            if action == "check_hire":
                alternatives = self.find_alternatives(
                    db,
                    venue,
                    start,
                    end,
                    content.get("guest_count", 0)
                )

            return self.send_message(
                message["sender"],
                "PROPOSE",
                {
                    "reason": "Requested venue or time is unavailable",
                    "alternatives": alternatives
                },
                conversation_id
            )

        except Exception as error:

            db.rollback()

            return self.send_message(
                message["sender"],
                "FAILURE",
                {"reason": str(error)},
                conversation_id
            )

        finally:
            db.close()
