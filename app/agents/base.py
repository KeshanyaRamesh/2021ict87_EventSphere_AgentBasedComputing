import json
import uuid
from datetime import datetime

from app.database import SessionLocal
from app.models import AgentMessage, AgentState


PERFORMATIVES = {
    "REQUEST",
    "AGREE",
    "REFUSE",
    "PROPOSE",
    "INFORM",
    "FAILURE"
}


class MessageBus:
    """
    Central communication system.
    Agents exchange structured JSON messages through this bus.
    Every message is saved in the database.
    """

    @staticmethod
    def send(sender, receiver, performative, content, conversation_id=None):

        if performative not in PERFORMATIVES:
            raise ValueError("Invalid message performative")

        conversation_id = conversation_id or str(uuid.uuid4())

        message_data = {
            "sender": sender,
            "receiver": receiver,
            "performative": performative,
            "content": content,
            "conversation_id": conversation_id
        }

        db = SessionLocal()

        try:
            message = AgentMessage(
                sender=sender,
                receiver=receiver,
                performative=performative,
                content=json.dumps(message_data["content"]),
                conversation_id=conversation_id,
                created_at=datetime.utcnow()
            )

            db.add(message)
            db.commit()

            return message_data

        finally:
            db.close()

    @staticmethod
    def inbox(agent_name):

        db = SessionLocal()

        try:
            messages = (
                db.query(AgentMessage)
                .filter(AgentMessage.receiver == agent_name)
                .order_by(AgentMessage.id.asc())
                .all()
            )

            return [
    {
        "message_id": msg.id,
        "sender": msg.sender,
        "receiver": msg.receiver,
        "performative": msg.performative,
        "content": json.loads(msg.content),
        "conversation_id": msg.conversation_id
    }
    for msg in messages
]

        finally:
            db.close()


class BaseAgent:
    """
    Base class for all EventSphere agents.
    Each agent has its own identity, beliefs and decision rules.
    """

    def __init__(self, name):
        self.name = name
        self.bus = MessageBus()

    def send_message(self, receiver, performative, content, conversation_id=None):
        return self.bus.send(
            self.name,
            receiver,
            performative,
            content,
            conversation_id
        )

    def get_messages(self):
        return self.bus.inbox(self.name)

    def get_belief(self, key, default=None):
        db = SessionLocal()

        try:
            state = (
                db.query(AgentState)
                .filter(
                    AgentState.agent_name == self.name,
                    AgentState.state_key == key
                )
                .first()
            )

            if state:
                return json.loads(state.state_value)

            return default

        finally:
            db.close()

    def save_belief(self, key, value):
        db = SessionLocal()

        try:
            state = (
                db.query(AgentState)
                .filter(
                    AgentState.agent_name == self.name,
                    AgentState.state_key == key
                )
                .first()
            )

            if state:
                state.state_value = json.dumps(value)
            else:
                state = AgentState(
                    agent_name=self.name,
                    state_key=key,
                    state_value=json.dumps(value)
                )
                db.add(state)

            db.commit()

        finally:
            db.close()

    def process_message(self, message):
        raise NotImplementedError(
            "Each agent must implement its own decision rules."
        )