
"""
NFL Season Simulation Engine
Handles full-season scheduling, standings, playoff seeding, and bracket management.
"""
 
import uuid
import random
from typing import Dict, List, Optional
from collections import defaultdict
 
from NFL_Simulator.data.entities.team import Team
from NFL_Simulator.data.entities.game import Game
from NFL_Simulator.simulation.game_engine import GameEngine
 
 
# 18-week regular season (17 games per team, 1 bye week)
REGULAR_SEASON_WEEKS = 18
PLAYOFF_TEAMS_PER_CONF = 7   # 4 division winners + 3 wild cards
 
DIVISIONS = [
    "AFC East", "AFC North", "AFC South", "AFC West",
    "NFC East", "NFC North", "NFC South", "NFC West",
]
 
PLAYOFF_ROUNDS = ["wildcard", "divisional", "conference", "superbowl"]
 
 
class SeasonEngine:
    """
    Manages an entire NFL season:
      - Schedule generation
      - Week-by-week simulation
      - Standings calculation
      - Playoff bracket generation and simulation
    """
 
    def __init__(self, season: int, teams: Dict[str, Team], seed: int = None):
        self.season = season
        self.teams = teams          # abbreviation → Team
        self.rng = random.Random(seed)
        self.game_engine = GameEngine(seed)
        self.schedule: List[Game] = []
        self.playoff_games: List[Game] = []
        self.current_week = 0
        self.byes: Dict[str, int] = {}   # abbr → bye week number
        self._built = False
 
    # ------------------------------------------------------------------
    # Schedule Building
    # ------------------------------------------------------------------
 
    def build_schedule(self):
        """Generate a simplified 18-week, 17-game-per-team schedule."""
        teams = list(self.teams.values())
        games: List[Game] = []
        home_counts: Dict[str, int] = defaultdict(int)

        bye_slots = list(range(5, 13)) * 4
        self.rng.shuffle(bye_slots)
        self.byes = {
            abbr: bye_slots[i]
            for i, abbr in enumerate(self.teams.keys())
        }

        for week in range(1, REGULAR_SEASON_WEEKS + 1):
            available = [
                team for team in teams
                if self.byes[team.abbreviation] != week
            ]
            self.rng.shuffle(available)

            while available:
                team_a = available.pop()
                team_b = available.pop()

                if home_counts[team_a.abbreviation] < home_counts[team_b.abbreviation]:
                    home, away = team_a, team_b
                elif home_counts[team_b.abbreviation] < home_counts[team_a.abbreviation]:
                    home, away = team_b, team_a
                elif self.rng.random() < 0.5:
                    home, away = team_a, team_b
                else:
                    home, away = team_b, team_a

                home_counts[home.abbreviation] += 1
                games.append(Game(
                    game_id=str(uuid.uuid4()),
                    week=week,
                    home_team=home.abbreviation,
                    away_team=away.abbreviation,
                    season=self.season,
                ))

        self.schedule = sorted(games, key=lambda x: (x.week, x.away_team, x.home_team))
        self._built = True
 
    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------
 
    def simulate_week(self, week: int) -> List[Game]:
        """Simulate all games in a given week."""
        week_games = [g for g in self.schedule if g.week == week and not g.is_completed]
        for game in week_games:
            home = self.teams[game.home_team]
            away = self.teams[game.away_team]
            self.game_engine.simulate(game, home, away)
 
        # Apply bye weeks
        for abbr, bye_week in self.byes.items():
            if bye_week == week:
                self.teams[abbr].apply_bye_week()
 
        self.current_week = max(self.current_week, week)
        return week_games
 
    def simulate_full_season(self) -> List[Game]:
        """Simulate the entire regular season."""
        if not self._built:
            self.build_schedule()
        for week in range(1, REGULAR_SEASON_WEEKS + 1):
            self.simulate_week(week)
        return self.schedule

    @property
    def regular_season_complete(self) -> bool:
        return bool(self.schedule) and all(game.is_completed for game in self.schedule)

    def next_unsimulated_week(self) -> Optional[int]:
        for week in range(1, REGULAR_SEASON_WEEKS + 1):
            if any(game.week == week and not game.is_completed for game in self.schedule):
                return week
        return None
 
    def simulate_game(self, game: Game) -> Game:
        """Simulate a single specific game."""
        home = self.teams[game.home_team]
        away = self.teams[game.away_team]
        return self.game_engine.simulate(game, home, away)
 
    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------
 
    def get_standings(self) -> Dict[str, List[dict]]:
        """Return standings grouped by division."""
        divisions: Dict[str, List[Team]] = defaultdict(list)
        for t in self.teams.values():
            divisions[t.division].append(t)
 
        result = {}
        for div in DIVISIONS:
            div_teams = sorted(
                divisions.get(div, []),
                key=lambda t: (-t.win_pct, -t.point_differential, -t.points_for)
            )
            result[div] = [self._team_standing_dict(t) for t in div_teams]
        return result
 
    def get_conference_standings(self, conference: str) -> List[dict]:
        """Return standings for one conference."""
        teams = [t for t in self.teams.values() if t.conference == conference]
        sorted_teams = sorted(
            teams,
            key=lambda t: (-t.win_pct, -t.point_differential, -t.points_for)
        )
        return [self._team_standing_dict(t) for t in sorted_teams]
 
    def _team_standing_dict(self, t: Team) -> dict:
        gp = t.games_played
        return {
            "abbreviation": t.abbreviation,
            "full_name": t.full_name,
            "conference": t.conference,
            "division": t.division,
            "wins": t.wins,
            "losses": t.losses,
            "ties": t.ties,
            "win_pct": round(t.win_pct, 3),
            "points_for": t.points_for,
            "points_against": t.points_against,
            "point_differential": t.point_differential,
            "overall_rating": round(t.overall_rating, 1),
            "playoff_seed": t.playoff_seed,
            "is_division_winner": t.is_division_winner,
            "is_wildcard": t.is_wildcard,
            "games_played": gp,
            "total_yards": t.total_yards,
            "passing_yards": t.passing_yards,
            "rushing_yards": t.rushing_yards,
            "touchdowns": t.touchdowns,
            "interceptions": t.interceptions,
            "yards_per_game": round(t.total_yards / gp, 1) if gp else 0.0,
            "passing_yards_pg": round(t.passing_yards / gp, 1) if gp else 0.0,
            "rushing_yards_pg": round(t.rushing_yards / gp, 1) if gp else 0.0,
        }

    def _rank_teams(self, rows: List[dict], sort_key, reverse: bool = True) -> List[dict]:
        ranked = sorted(rows, key=sort_key, reverse=reverse)
        for index, row in enumerate(ranked, start=1):
            row["rank"] = index
        return ranked

    def get_power_rankings(self) -> List[dict]:
        """Rank teams by record and point differential."""
        rows = [self._team_standing_dict(t) for t in self.teams.values() if t.games_played > 0]
        return self._rank_teams(
            rows,
            lambda row: (row["win_pct"], row["point_differential"], row["points_for"]),
        )

    def get_team_stat_rankings(self, category: str) -> List[dict]:
        """Rank teams by a cumulative season stat category."""
        valid = {
            "passing_yards",
            "rushing_yards",
            "total_yards",
            "touchdowns",
            "interceptions",
            "yards_per_game",
            "passing_yards_pg",
            "rushing_yards_pg",
        }
        if category not in valid:
            raise ValueError(f"Category must be one of: {sorted(valid)}")

        rows = [self._team_standing_dict(t) for t in self.teams.values() if t.games_played > 0]
        return self._rank_teams(rows, lambda row: row[category])

    def get_all_team_stat_rankings(self) -> Dict[str, List[dict]]:
        """Return league leaderboards for common team stat categories."""
        categories = [
            "passing_yards",
            "rushing_yards",
            "total_yards",
            "touchdowns",
            "yards_per_game",
        ]
        return {category: self.get_team_stat_rankings(category) for category in categories}
 
    # ------------------------------------------------------------------
    # Playoff Seeding
    # ------------------------------------------------------------------
 
    def calculate_playoff_seeds(self):
        """Determine playoff seeds for both conferences."""
        for team in self.teams.values():
            team.playoff_seed = None
            team.is_division_winner = False
            team.is_wildcard = False
        for conf in ["AFC", "NFC"]:
            self._seed_conference(conf)
 
    def _seed_conference(self, conference: str):
        """Assign seeds 1-7 for a conference."""
        divisions = [d for d in DIVISIONS if d.startswith(conference)]
        div_winners: List[Team] = []
 
        for div in divisions:
            div_teams = [t for t in self.teams.values() if t.division == div]
            winner = max(div_teams, key=lambda t: (t.win_pct, t.point_differential, t.points_for))
            winner.is_division_winner = True
            div_winners.append(winner)
 
        div_winner_abbrs = {t.abbreviation for t in div_winners}
 
        # Sort division winners by record (seed 1-4)
        div_winners.sort(key=lambda t: (-t.win_pct, -t.point_differential))
 
        # Wild card teams (seeds 5-7)
        conf_teams = [t for t in self.teams.values()
                      if t.conference == conference and t.abbreviation not in div_winner_abbrs]
        conf_teams.sort(key=lambda t: (-t.win_pct, -t.point_differential))
        wildcards = conf_teams[:3]
        for wc in wildcards:
            wc.is_wildcard = True
 
        for i, t in enumerate(div_winners):
            t.playoff_seed = i + 1
        for i, t in enumerate(wildcards):
            t.playoff_seed = i + 5
 
    def get_playoff_seeds(self) -> Dict[str, List[dict]]:
        """Return seeded playoff teams per conference."""
        result = {}
        for conf in ["AFC", "NFC"]:
            seeds = [
                t for t in self.teams.values()
                if t.conference == conf and t.playoff_seed is not None
            ]
            seeds.sort(key=lambda t: t.playoff_seed)
            result[conf] = [self._team_standing_dict(t) for t in seeds]
        return result
 
    # ------------------------------------------------------------------
    # Playoff Simulation
    # ------------------------------------------------------------------
 
    def build_playoff_bracket(self) -> Dict:
        """Build the initial playoff bracket."""
        if not self.regular_season_complete:
            raise ValueError("Regular season must be complete before building playoffs.")
        self.calculate_playoff_seeds()
        self.playoff_games = []
        bracket = {"AFC": {}, "NFC": {}, "superbowl": None}
 
        for conf in ["AFC", "NFC"]:
            seeds = {
                t.playoff_seed: t
                for t in self.teams.values()
                if t.conference == conf and t.playoff_seed is not None
            }
            # Wild Card matchups: (2v7), (3v6), (4v5); seed 1 gets bye
            wc_games = [
                self._make_playoff_game(seeds[2], seeds[7], "wildcard", conf),
                self._make_playoff_game(seeds[3], seeds[6], "wildcard", conf),
                self._make_playoff_game(seeds[4], seeds[5], "wildcard", conf),
            ]
            bracket[conf]["wildcard"] = [g.to_dict() for g in wc_games]
            self.playoff_games.extend(wc_games)
 
        return bracket
 
    def simulate_playoff_round(self, round_name: str) -> Dict:
        """
        Simulate all games in a playoff round and advance winners.
        Returns updated bracket info.
        """
        self._validate_playoff_round_ready(round_name)
        round_games = [g for g in self.playoff_games if g.playoff_round == round_name]
        results = []
        for game in round_games:
            if not game.is_completed:
                home = self.teams[game.home_team]
                away = self.teams[game.away_team]
                self.game_engine.simulate(game, home, away)
            results.append(game.to_dict())
 
        # Advance winners and schedule next round
        if round_name == "wildcard":
            self._schedule_divisional()
        elif round_name == "divisional":
            self._schedule_conference()
        elif round_name == "conference":
            self._schedule_superbowl()
 
        return {"round": round_name, "games": results}

    def _validate_playoff_round_ready(self, round_name: str):
        if round_name not in PLAYOFF_ROUNDS:
            raise ValueError(f"Round must be one of: {PLAYOFF_ROUNDS}")

        if not self.playoff_games:
            raise ValueError("Build the playoff bracket before simulating playoff games.")

        round_games = [g for g in self.playoff_games if g.playoff_round == round_name]
        if not round_games:
            raise ValueError(f"No {round_name} games are scheduled yet.")

        round_index = PLAYOFF_ROUNDS.index(round_name)
        if round_index == 0:
            return

        previous_round = PLAYOFF_ROUNDS[round_index - 1]
        previous_games = [g for g in self.playoff_games if g.playoff_round == previous_round]
        if not previous_games or not all(g.is_completed for g in previous_games):
            raise ValueError(f"Complete the {previous_round} round first.")
 
    def _schedule_divisional(self):
        """Schedule divisional games using seeds."""
        if any(g.playoff_round == "divisional" for g in self.playoff_games):
            return
        for conf in ["AFC", "NFC"]:
            seeds = {
                t.playoff_seed: t
                for t in self.teams.values()
                if t.conference == conf and t.playoff_seed is not None
            }
            seed1 = seeds[1]
 
            # WC winners sorted by their original seed
            wc_winners = self._get_round_winners("wildcard", conf)
            wc_winners.sort(key=lambda t: t.playoff_seed)
 
            if len(wc_winners) >= 3:
                # 1 vs lowest remaining seed
                self.playoff_games.append(
                    self._make_playoff_game(seed1, wc_winners[2], "divisional", conf)
                )
                self.playoff_games.append(
                    self._make_playoff_game(wc_winners[0], wc_winners[1], "divisional", conf)
                )
 
    def _schedule_conference(self):
        """Schedule conference championship games."""
        if any(g.playoff_round == "conference" for g in self.playoff_games):
            return
        for conf in ["AFC", "NFC"]:
            winners = self._get_round_winners("divisional", conf)
            if len(winners) >= 2:
                winners.sort(key=lambda t: t.playoff_seed)
                self.playoff_games.append(
                    self._make_playoff_game(winners[0], winners[1], "conference", conf)
                )
 
    def _schedule_superbowl(self):
        """Schedule the Super Bowl."""
        if any(g.playoff_round == "superbowl" for g in self.playoff_games):
            return
        afc_champ = self._get_round_winners("conference", "AFC")
        nfc_champ = self._get_round_winners("conference", "NFC")
        if afc_champ and nfc_champ:
            game = self._make_playoff_game(afc_champ[0], nfc_champ[0], "superbowl", "")
            game.neutral_site = True
            self.playoff_games.append(game)
 
    def _get_round_winners(self, round_name: str, conference: str) -> List[Team]:
        """Return Team objects that won games in a given playoff round."""
        round_games = [
            g for g in self.playoff_games
            if g.playoff_round == round_name and g.is_completed
        ]
        if conference:
            conf_teams = {t.abbreviation for t in self.teams.values() if t.conference == conference}
            round_games = [
                g for g in round_games
                if g.home_team in conf_teams or g.away_team in conf_teams
            ]
        winners = []
        for g in round_games:
            if g.winner and g.winner != "TIE":
                winners.append(self.teams[g.winner])
        return winners
 
    def _make_playoff_game(
        self, higher_seed: Team, lower_seed: Team,
        round_name: str, conference: str
    ) -> Game:
        return Game(
            game_id=str(uuid.uuid4()),
            week=REGULAR_SEASON_WEEKS + PLAYOFF_ROUNDS.index(round_name) + 1,
            home_team=higher_seed.abbreviation,
            away_team=lower_seed.abbreviation,
            season=self.season,
            is_playoff=True,
            playoff_round=round_name,
        )
 
    def get_all_playoff_games(self) -> List[dict]:
        return [g.to_dict() for g in self.playoff_games]

    def playoffs_started(self) -> bool:
        return bool(self.playoff_games)

    def get_active_playoff_teams(self) -> set:
        """Return abbreviations of teams still alive in the playoffs."""
        if not self.playoff_games:
            return {t.abbreviation for t in self.teams.values()}

        seeded = {
            t.abbreviation for t in self.teams.values()
            if t.playoff_seed is not None
        }
        eliminated = set()
        for game in self.playoff_games:
            if not game.is_completed or not game.winner or game.winner == "TIE":
                continue
            loser = game.away_team if game.winner == game.home_team else game.home_team
            eliminated.add(loser)

        return seeded - eliminated

    def get_champion(self) -> Optional[dict]:
        """Return the Super Bowl winner if completed."""
        sb = next((g for g in self.playoff_games if g.playoff_round == "superbowl" and g.is_completed), None)
        if sb and sb.winner:
            t = self.teams.get(sb.winner)
            return self._team_standing_dict(t) if t else None
        return None
