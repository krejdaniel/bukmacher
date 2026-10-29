from sqlalchemy import Column, Integer, String, Float, Date

from app.database.database import Base


class TrainingMatch(Base):

    __tablename__ = "training_matches"


    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    match_id = Column(
        Integer,
        nullable=False
    )


    date = Column(
        Date,
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


    home_points = Column(
        Float
    )


    home_avg_goals = Column(
        Float
    )


    home_avg_conceded = Column(
        Float
    )


    away_points = Column(
        Float
    )


    away_avg_goals = Column(
        Float
    )


    away_avg_conceded = Column(
        Float
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

    home_goal_difference = Column(Float)

    home_points_per_match = Column(Float)

    home_clean_sheet_rate = Column(Float)

    home_failed_to_score_rate = Column(Float)

    away_goal_difference = Column(Float)

    away_points_per_match = Column(Float)

    away_clean_sheet_rate = Column(Float)

    away_failed_to_score_rate = Column(Float)

    home_implied_prob = Column(Float)

    draw_implied_prob = Column(Float)

    away_implied_prob = Column(Float)
    
    home_all_points = Column(Float)

    home_all_avg_goals = Column(Float)

    home_all_avg_conceded = Column(Float)

    away_all_points = Column(Float)

    away_all_avg_goals = Column(Float)

    away_all_avg_conceded = Column(Float)

    home_last3_points = Column(Float)

    away_last3_points = Column(Float)

    home_last3_avg_goals = Column(Float)

    away_last3_avg_goals = Column(Float)

    home_elo = Column(Float)

    away_elo = Column(Float)

    elo_diff = Column(Float)
    
    home_attack_rating = Column(Float)
    home_defense_rating = Column(Float)

    away_attack_rating = Column(Float)
    away_defense_rating = Column(Float)
    
    home_avg_xg = Column(Float)

    away_avg_xg = Column(Float)

    home_avg_xga = Column(Float)

    away_avg_xga = Column(Float)

    result = Column(
        String(1)
    )