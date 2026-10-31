"""
NFL Team Data Model 
Represents an NFL team with all attributes needed for simulation
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from NFL_Simulator.data.entities.game import GameStats

@dataclass
class Team:
    name        : str
    abbreviation : str
    city        : str
    conference   : str
    division     : str

    #Core Ratings 
    offensive_rating : float  = 75.0
    defensive_rating : float  = 75.0
    special_teams_rating : float = 75.0
    coaching_rating : float = 75.0

    #Dynamic Attributes 
    morale : float = 75.0
    fatigue : float = 0.0
    fan_support : float = 75.0

    #Injury Impact 
    injury_status : float = 0.0

    #Season Record 
    wins            : int = 0
    losses          : int = 0 
    ties            : int = 0
    points_for      : int = 0
    points_against  : int = 0 
    division_wins   : int = 0
    conference_wins : int = 0

    # Season stat totals
    total_yards     : int = 0
    passing_yards   : int = 0
    rushing_yards   : int = 0
    touchdowns      : int = 0
    interceptions   : int = 0
    turnovers_forced: int = 0
    sacks           : int = 0

    #Playoff tracker
    playoff_seed        : Optional[int] = None
    is_division_winner : bool = False
    is_wildcard         : bool = False

    @property
    def full_name(self) -> str:
        return f"{self.city} {self.name}"
    
    @property
    def overall_rating(self) ->float:
        return(
            self.offensive_rating * 0.35 + 
            self.defensive_rating * 0.35 + 
            self.coaching_rating * 0.15 +
            self.special_teams_rating * 0.15
        )
    
    @property
    def win_pct(self) -> float:
        games = self.wins + self.losses + self.ties
        if games == 0:
            return 0.0
        return (self.wins + 0.5 * self.ties) / games
    
    @property
    def point_differential(self) -> int:
        return self.points_for - self.points_against
    
    @property
    def games_played(self) -> int:
       return self.wins + self.losses + self.ties
    
    def effective_offensive_rating(self) ->float:
        fatigue_penalty = self.fatigue * 0.08
        morale_bonus = (self.morale - 75) * 0.06
        injury_penalty = self.injury_status * 0.10
        return max (10, min(99,
            self.offensive_rating - fatigue_penalty + morale_bonus - injury_penalty ))

    def effective_defensive_rating(self) ->float:
        fatigue_penalty = self.fatigue * 0.06
        morale_bonus = (self.morale - 75) * 0.04
        injury_penalty = self.injury_status * 0.08
        return max(10, min(99,
            self.defensive_rating - fatigue_penalty + morale_bonus - injury_penalty))
    
    def record_str(self) -> str:
        if self.ties > 0:
            return f"{self.wins}-{self.losses}-{self.ties}"
        return f"{self.wins}-{self.losses}"


    def apply_game_result(self, scored : int, allowed : int, won : bool, tied : bool = False):
        self.points_for += scored
        self.points_against += allowed
        if tied:
            self.ties += 1
        elif won:
            self.wins += 1
            self.morale = min(100,self.morale + 5)
        else:
            self.losses += 1
            self.morale = max(0, self.morale - 5)     

        self.fatigue = min(100, self.fatigue + 10)

    def apply_game_stats(self, stats: "GameStats"):
        self.total_yards += stats.total_yards
        self.passing_yards += stats.passing_yards
        self.rushing_yards += stats.rushing_yards
        self.touchdowns += stats.touchdowns
        self.interceptions += stats.interceptions
        self.turnovers_forced += stats.turnovers_forced
        self.sacks += stats.sacks

    def apply_bye_week(self):
        self.fatigue = max(0 , self.fatigue - 30)
        self.injury_status = max(0, self.injury_status - 10)

    def reset_season(self):
        self.wins = 0
        self.losses = 0 
        self.ties = 0 
        self.points_for = 0
        self.points_against = 0 
        self.division_wins = 0 
        self.conference_wins = 0 
        self.fatigue = 0.0
        self.injury_status = 0.0
        self.morale = 75.0
        self.total_yards = 0
        self.passing_yards = 0
        self.rushing_yards = 0
        self.touchdowns = 0
        self.interceptions = 0
        self.turnovers_forced = 0
        self.sacks = 0
        self.playoff_seed = None
        self.is_division_winner = False
        self.is_wildcard = False

    def to_dict(self) -> dict:
        gp = self.games_played
        data = asdict(self)
        data["overall_rating"] = round(self.overall_rating, 1)
        data["win_pct"] = round(self.win_pct, 3)
        data["point_differential"] = self.point_differential
        data["games_played"] = gp
        data["yards_per_game"] = round(self.total_yards / gp, 1) if gp else 0.0
        data["passing_yards_pg"] = round(self.passing_yards / gp, 1) if gp else 0.0
        data["rushing_yards_pg"] = round(self.rushing_yards / gp, 1) if gp else 0.0
        return data
    
    @classmethod
    def from_dict(cls, data :dict) -> "Team":
        return cls(**{k : v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def __repr__(self):
        return f"<Team {self.full_name} ({self.record_str()}) OVR={self.overall_rating:.1f}>"
