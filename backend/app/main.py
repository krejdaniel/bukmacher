from app.database.database import Base, engine
from app.models.match import Match
from app.models.training_match import TrainingMatch

print("Tworzenie tabel...")


Base.metadata.create_all(
    bind=engine
)


print("Gotowe!")