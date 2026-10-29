from sqlalchemy import Column, Integer, String, Date, Float

from app.database.database import Base


class Match(Base):

    __tablename__ = "matches"


    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    date = Column(
        Date,
        nullable=False
    )


    season = Column(
        String,
        nullable=False
    )


    home_team = Column(
        String,
        nullable=False
    )


    away_team = Column(
        String,
        nullable=False
    )


    home_goals = Column(
        Integer
    )


    away_goals = Column(
        Integer
    )


    home_odds = Column(
        Float
    )


    draw_odds = Column(
        Float
    )


    away_odds = Column(
        Float
    )
    
    home_xg = Column(Float)
    away_xg = Column(Float)
    
    result = Column(
    String(1)
    )