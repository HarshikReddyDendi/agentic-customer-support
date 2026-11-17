from app.database.connection import engine, Base
from app.database import models


_registered_models = (
    models.Customer,
    models.Order,
    models.SupportTicket,
    models.ConversationMessage,
    models.SupportEscalation,
)


def initialize_database():
    Base.metadata.create_all(bind=engine)
    print("Customer Support Database Created Successfully!")


if __name__ == "__main__":
    initialize_database()
