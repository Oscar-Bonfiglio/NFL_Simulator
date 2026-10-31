import math
import random
from typing import Tuple

from NFL_Simulator.data.entities.game import Game, GameStats, GameStatus, WeatherCondition
from NFL_Simulator.data.entities.team import Team


WEATHER_EFFECTS = {
    WeatherCondition.CLEAR: {"passing": 1.00, "scoring": 1.00, "fg": 1.00},
    WeatherCondition.CLOUDY: {"passing": 0.97, "scoring": 0.97, "fg": 0.98},
    WeatherCondition.RAIN: {"passing": 0.88, "scoring": 0.88, "fg": 0.88},
    WeatherCondition.SNOW: {"passing": 0.82, "scoring": 0.82, "fg": 0.82},
    WeatherCondition.WIND: {"passing": 0.84, "scoring": 0.84, "fg": 0.78},
    WeatherCondition.DOME: {"passing": 1.05, "scoring": 1.05, "fg": 1.05},
}

DOME_TEAMS = {"IND", "NO", "ATL", "LV", "LAR", "LAC", "MIN", "DAL", "HOU", "DET", "ARI"}


class GameEngine:
    def __init__(self, seed: int = None):
        self.rng = random.Random(seed)

    def simulate(self, game: Game, home: Team, away: Team) -> Game:
        weather = self._resolve_weather(game, home)
        wx = WEATHER_EFFECTS[weather]
        game.weather = weather

        hfa = 0.0 if game.neutral_site else game.home_field_advantage
        home_wp = self._win_probability(home, away, hfa)
        game.home_win_probability = round(home_wp, 3)

        home_score, away_score, home_stats, away_stats = self._generate_scores(
            home, away, hfa, wx
        )

        if home_score == away_score:
            if self.rng.random() < 0.5:
                home_score += 3
            else:
                away_score += 3
            home_stats.score = home_score
            away_stats.score = away_score

        game.home_score = home_score
        game.away_score = away_score
        game.home_stats = home_stats
        game.away_stats = away_stats
        game.status = GameStatus.COMPLETED

        home_won = home_score > away_score
        away_won = away_score > home_score
        if home_won:
            game.winner = home.abbreviation
        elif away_won:
            game.winner = away.abbreviation
        else:
            game.winner = "TIE"

        home.apply_game_result(home_score, away_score, home_won, tied=not home_won and not away_won)
        away.apply_game_result(away_score, home_score, away_won, tied=not home_won and not away_won)
        home.apply_game_stats(home_stats)
        away.apply_game_stats(away_stats)

        return game

    def _win_probability(self, home: Team, away: Team, hfa: float) -> float:
        home_str = home.effective_offensive_rating() * 0.5 + home.effective_defensive_rating() * 0.5
        away_str = away.effective_offensive_rating() * 0.5 + away.effective_defensive_rating() * 0.5

        coaching_delta = (home.coaching_rating - away.coaching_rating) * 0.15
        morale_delta = (home.morale - away.morale) * 0.05
        fan_delta = (home.fan_support - away.fan_support) * 0.03

        diff = (home_str - away_str) + hfa + coaching_delta + morale_delta + fan_delta
        wp = 1 / (1 + math.exp(-diff / 12))
        return max(0.05, min(0.95, wp))

    def _generate_scores(
        self,
        home: Team,
        away: Team,
        hfa: float,
        wx: dict,
    ) -> Tuple[int, int, GameStats, GameStats]:
        home_offense = home.effective_offensive_rating()
        away_offense = away.effective_offensive_rating()
        home_defense = home.effective_defensive_rating()
        away_defense = away.effective_defensive_rating()

        home_exp = self._expected_score(home_offense, away_defense, hfa, wx)
        away_exp = self._expected_score(away_offense, home_defense, 0, wx)
        home_score, away_score = self._score_with_drives(home_exp), self._score_with_drives(away_exp)

        home_stats = self._generate_team_stats(home, away, home_score, wx, is_home=True)
        away_stats = self._generate_team_stats(away, home, away_score, wx, is_home=False)
        return home_score, away_score, home_stats, away_stats

    def _expected_score(self, offense: float, defense: float, hfa: float, wx: dict) -> float:
        base = 17 + (offense - 75) * 0.22 - (defense - 75) * 0.22
        base += hfa * 0.5
        base *= wx["scoring"]
        return max(3.0, base)

    def _score_with_drives(self, expected_points: float) -> int:
        possessions = self.rng.randint(9, 13)
        quality = max(-1.0, min(1.0, (expected_points - 20.0) / 12.0))
        td_prob = max(0.08, min(0.34, 0.20 + quality * 0.08))
        fg_prob = max(0.10, min(0.27, 0.18 + quality * 0.03))
        safety_prob = 0.003

        score = 0
        for _ in range(possessions):
            roll = self.rng.random()
            if roll < safety_prob:
                score += 2
            elif roll < safety_prob + td_prob:
                score += self._touchdown_points()
            elif roll < safety_prob + td_prob + fg_prob:
                score += 3

        # Keep rare shutouts, but avoid absurdly tiny modern NFL scores.
        if score in (1, 4, 5):
            score = 3 if score < 5 else 6
        if score > 49:
            score = self.rng.choice([49, 50, 51, 52, 53, 56])
        return score

    def _touchdown_points(self) -> int:
        roll = self.rng.random()
        if roll < 0.90:
            return 7
        if roll < 0.97:
            return 6
        return 8

    def _generate_team_stats(
        self,
        offense: Team,
        defense: Team,
        score: int,
        wx: dict,
        is_home: bool,
    ) -> GameStats:
        stats = GameStats(team_abbr=offense.abbreviation, score=score)

        off_r = offense.effective_offensive_rating()
        def_r = defense.effective_defensive_rating()
        quality = max(0.0, min(1.0, (off_r - def_r) / 100 + 0.5))

        stats.total_yards = int(self._gauss_clamp(280 + quality * 130, 45, 150, 500))

        pass_share = self.rng.uniform(0.55, 0.70) * wx["passing"]
        stats.passing_yards = int(stats.total_yards * pass_share)
        stats.rushing_yards = stats.total_yards - stats.passing_yards

        stats.attempts = int(self._gauss_clamp(32 + quality * 6, 5, 18, 55))
        comp_rate = self._gauss_clamp(0.60 + quality * 0.10, 0.05, 0.45, 0.80)
        comp_rate *= wx["passing"]
        stats.completions = int(stats.attempts * comp_rate)

        td_base = score / 7.0
        stats.touchdowns = int(self._gauss_clamp(td_base, 0.5, 0, 6))

        int_rate = max(0, 0.025 - quality * 0.012)
        stats.interceptions = self._poisson(int_rate * stats.attempts)
        stats.turnovers_forced = self._poisson(0.5 + (1 - quality) * 0.8)

        stats.sacks = self._poisson(1.5 + (1 - quality) * 1.5)
        stats.sacks_allowed = self._poisson(1.5 + (1 - quality) * 1.0)

        fg_attempts = max(0, round(self._gauss_clamp(2.2 - quality * 0.8, 0.6, 0, 5)))
        fg_rate = (0.82 + quality * 0.06) * wx["fg"]
        stats.field_goals_attempted = fg_attempts
        stats.field_goals_made = sum(1 for _ in range(fg_attempts) if self.rng.random() < fg_rate)

        stats.third_down_attempts = int(self._gauss_clamp(13, 2, 7, 20))
        conv_rate = 0.38 + quality * 0.12
        stats.third_down_conversions = int(stats.third_down_attempts * conv_rate)

        stats.red_zone_attempts = max(1, int(score / 7) + self.rng.randint(0, 2))
        stats.red_zone_scores = int(stats.red_zone_attempts * (0.55 + quality * 0.15))

        stats.penalty_yards = int(self._gauss_clamp(50, 15, 10, 110))
        stats.time_of_possession = round(
            self._gauss_clamp(28 + quality * 4 + (2 if is_home else 0), 3, 18, 42),
            1,
        )

        return stats

    def _gauss_clamp(self, mean: float, std: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, self.rng.gauss(mean, std)))

    def _poisson(self, lam: float) -> int:
        if lam <= 0:
            return 0
        limit = math.exp(-lam)
        k, p = 0, 1.0
        while p > limit:
            k += 1
            p *= self.rng.random()
        return max(0, k - 1)

    def _resolve_weather(self, game: Game, home: Team) -> WeatherCondition:
        if home.abbreviation in DOME_TEAMS:
            return WeatherCondition.DOME
        return game.weather if isinstance(game.weather, WeatherCondition) else WeatherCondition(game.weather)
