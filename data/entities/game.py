from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class WeatherCondition(str, Enum):
    CLEAR = "Clear"
    CLOUDY = "Cloudy"
    RAIN = "Rain"
    SNOW = "Snow"
    WIND = "Wind"
    DOME = "Dome"

class GameStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"

@dataclass
class GameStats:
    team_abbr : str
    score : int = 0 

    #Offensive
    total_yards     : int = 0 
    passing_yards   : int = 0 
    rushing_yards   : int = 0 
    completions     : int = 0 
    attempts        : int = 0
    touchdowns      : int = 0
    interceptions   : int = 0
    sacks_allowed   : int = 0 

    #Defensive 
    sacks            : int = 0 
    turnovers_forced : int = 0 

    #Special Teams
    field_goals_made     : int = 0
    field_goals_attempted : int = 0 

    #Efficiency 
    third_down_conversions : int = 0 
    third_down_attempts   : int = 0 
    red_zone_attempts     : int = 0 
    red_zone_scores       : int = 0
    penalty_yards         : int = 0 
    time_of_possession     : int = 0 

    @property
    def complection_pct(self) ->float:
        if self.attempts == 0:
            return 0
        return round(self.completions / self.attempts * 100, 1)
    
    @property
    def fg_pct(self) ->float:
        if self.field_goals_attempted == 0:
            return 0 
        return round(self.field_goals_made / self.field_goals_attempted * 100, 1)
    
    @property
    def third_down_pct(self) ->float:
        if self.third_down_attempts == 0:
            return 0
        return round(self.third_down_conversions / self.third_down_attempts * 100, 1)
    
    def to_dict(self) ->str:
        return {
            "team_abbr" : self.team_abbr,
            "score"     : self.score,
            "total_yards" : self.total_yards,
            "passing_yards": self.passing_yards,
            "rushing_yards": self.rushing_yards,
            "completions": self.completions,
            "attempts": self.attempts,
            "completion_pct": self.complection_pct,
            "touchdowns": self.touchdowns,
            "interceptions": self.interceptions,
            "sacks_allowed": self.sacks_allowed,
            "sacks": self.sacks,
            "turnovers_forced": self.turnovers_forced,
            "field_goals_made": self.field_goals_made,
            "field_goals_attempted": self.field_goals_attempted,
            "fg_pct": self.fg_pct,
            "third_down_conversions": self.third_down_conversions,
            "third_down_attempts": self.third_down_attempts,
            "third_down_pct": self.third_down_pct,
            "red_zone_scores": self.red_zone_scores,
            "red_zone_attempts": self.red_zone_attempts,
            "penalty_yards": self.penalty_yards,
            "time_of_possession": self.time_of_possession
        }

@dataclass
class Game:
    game_id         : str
    week            : int
    home_team       : str         
    away_team       : str         
    season          : int
    is_playoff      : bool = False
    playoff_round   : Optional[str] = None   
 
    # Pre-game conditions
    weather: WeatherCondition = WeatherCondition.CLEAR
    home_field_advantage: float = 3.0  
    neutral_site: bool = False
 
    # Results
    status: GameStatus = GameStatus.SCHEDULED
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    winner: Optional[str] = None
    home_win_probability: Optional[float] = None
 
    home_stats: Optional[GameStats] = None
    away_stats: Optional[GameStats] = None
 
    @property
    def is_completed(self) -> bool:
        return self.status == GameStatus.COMPLETED
 
    @property
    def score_display(self) -> str:
        if not self.is_completed:
            return "vs"
        return f"{self.away_score} - {self.home_score}"
 
    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "week": self.week,
            "season": self.season,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "is_playoff": self.is_playoff,
            "playoff_round": self.playoff_round,
            "weather": self.weather.value if isinstance(self.weather, WeatherCondition) else self.weather,
            "home_field_advantage": self.home_field_advantage,
            "neutral_site": self.neutral_site,
            "status": self.status.value if isinstance(self.status, GameStatus) else self.status,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "winner": self.winner,
            "home_win_probability": self.home_win_probability,
            "home_stats": self.home_stats.to_dict() if self.home_stats else None,
            "away_stats": self.away_stats.to_dict() if self.away_stats else None,
        }
 
    def __repr__(self):
        if self.is_completed:
            return f"<Game W{self.week}: {self.away_team} {self.away_score} @ {self.home_team} {self.home_score}>"
        return f"<Game W{self.week}: {self.away_team} @ {self.home_team} [scheduled]>"
 
