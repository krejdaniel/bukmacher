from app.database.database import SessionLocal

from app.services.training_generator import (
    generate_training_data
)



db = SessionLocal()


generate_training_data(db)


db.close()