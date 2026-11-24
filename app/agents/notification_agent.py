
from app.agents.base import BaseAgent


class NotificationAgent(BaseAgent):

    def __init__(self):
        super().__init__("NotificationAgent")

    def process_message(self, message):

        if message.get("performative") != "INFORM":
            return {
                "success": False,
                "reason": "NotificationAgent only processes INFORM messages"
            }

        content = message.get("content", {})
        user_id = content.get("user_id")

        if not user_id:
            return {
                "success": False,
                "reason": "Notification recipient is missing"
            }

        key = f"notifications_user_{user_id}"

        notifications = self.get_belief(key, [])

        notification_type = content.get("type", "general")

        # Update the original offer notification when the attendee claims
        # it or when the offer expires, so the website removes its action.
        related_waitlist_id = content.get("waitlist_id")
        if related_waitlist_id and notification_type in (
            "waitlist_claimed", "waitlist_offer_expired"
        ):
            new_status = (
                "claimed"
                if notification_type == "waitlist_claimed"
                else "expired"
            )
            for old_notification in notifications:
                if old_notification.get("waitlist_id") == related_waitlist_id:
                    old_notification["status"] = new_status

        notification = {
            "type": notification_type,
            "message": content.get("message", "You have a new notification"),
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
            "conversation_id": message.get("conversation_id")
        }

        # Keep actionable waitlist-offer details so the website can show
        # a Claim Ticket button for the correct attendee.
        for field in (
            "waitlist_id", "event_id", "category_id", "expires_at"
        ):
            if field in content:
                notification[field] = content[field]

        if notification_type == "waitlist_offer":
            notification["status"] = "active"

        notifications.append(notification)

        self.save_belief(key, notifications)

        return {
            "success": True,
            "user_id": user_id,
            "notification": notification
        }

    def process_inbox(self):

        messages = self.get_messages()

        processed = self.get_belief("processed_message_ids", [])

        results = []

        for message in messages:

            message_id = message.get("message_id")

            if message_id is None or message_id in processed:
                continue

            if message["performative"] == "INFORM":

                result = self.process_message(message)
                results.append(result)

            processed.append(message_id)

            self.save_belief("processed_message_ids", processed)

        return results

    def get_notifications(self, user_id):

        return self.get_belief(
            f"notifications_user_{user_id}",
            []
        )
