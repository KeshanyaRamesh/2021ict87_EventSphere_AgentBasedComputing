
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

        notification = {
            "type": content.get("type", "general"),
            "message": content.get("message", "You have a new notification"),
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
            "conversation_id": message.get("conversation_id")
        }

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
