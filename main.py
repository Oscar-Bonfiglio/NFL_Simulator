import json
import os
import copy
from typing import Dict, Optional
from flask import Flask, jsonify, request, send_from_directory
try:
    from flask_cors import CORS
except ImportError:
    CORS = None
 
from NFL_Simulator.data.entities.team import Team
from NFL_Simulator.data.entities.game import Game, WeatherCondition
from NFL_Simulator.simulation.game_engine import GameEngine
from NFL_Simulator.simulation.season_engine import SeasonEngine
 
# App Setup
app = Flask(__name__)
if CORS:
    CORS(app)
 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEAMS_JSON = os.path.join(BASE_DIR, "data", "teams.json")
 
 
# In-Memory State
class AppState:
    def __init__(self):
        self.teams: Dict[str, Team] = {}
        self.season_engine: Optional[SeasonEngine] = None
        self.season_year: int = 2024
        self.game_engine = GameEngine()
        self._load_teams()
 
    def _load_teams(self):
        with open(TEAMS_JSON) as f:
            data = json.load(f)
        self.teams = {}
        for td in data:
            t = Team.from_dict(td)
            self.teams[t.abbreviation] = t
 
    def reset_teams(self):
        self._load_teams()
        self.season_engine = None

    def new_season(self, year: int = 2024, seed: Optional[int] = None):
        for t in self.teams.values():
            t.reset_season()
        self.season_year = year
        self.season_engine = SeasonEngine(year, self.teams, seed=seed)
        self.season_engine.build_schedule()
 
 
state = AppState()
 
 
# Helpers
def ok(data=None, **kwargs):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return jsonify(payload)
 
 
def err(msg: str, code: int = 400):
    return jsonify({"success": False, "error": msg}), code
 
 
def require_season():
    if state.season_engine is None:
        return err("No active season. POST /api/season/new first.", 400)
    return None
 
 
# Metadata
@app.route("/", methods=["GET"])
def index():
    """Serve the browser interface without requiring a separate frontend server."""
    return send_from_directory(os.path.join(BASE_DIR, "static"), "index.html")


@app.route("/api/meta", methods=["GET"])
def get_meta():
    return ok({
        "weeks": 18,
        "weather_options": [weather.value for weather in WeatherCondition],
        "conferences": ["AFC", "NFC"],
        "playoff_rounds": ["wildcard", "divisional", "conference", "superbowl"],
    })


# Teams
@app.route("/api/teams", methods=["GET"])
def get_teams():
    """Return teams with current ratings and record.

    During an active playoff bracket, only teams still alive in the playoffs
    are included; eliminated and non-playoff teams are omitted.
    """
    teams = list(state.teams.values())
    if state.season_engine and state.season_engine.playoffs_started():
        active = state.season_engine.get_active_playoff_teams()
        teams = [t for t in teams if t.abbreviation in active]
    return ok([t.to_dict() for t in teams])
 
 
@app.route("/api/teams/<abbr>", methods=["GET"])
def get_team(abbr: str):
    t = state.teams.get(abbr.upper())
    if not t:
        return err(f"Team '{abbr}' not found.", 404)
    return ok(t.to_dict())
 
 
@app.route("/api/teams/<abbr>", methods=["PATCH"])
def update_team(abbr: str):
    """
    Partially update team attributes.
    Body: JSON object with any subset of team fields.
    """
    t = state.teams.get(abbr.upper())
    if not t:
        return err(f"Team '{abbr}' not found.", 404)
 
    body = request.get_json(force=True, silent=True) or {}
    editable = {
        "offensive_rating", "defensive_rating", "special_teams_rating",
        "coaching_rating", "morale", "fatigue", "fan_support", "injury_status"
    }
    for key, val in body.items():
        if key in editable:
            setattr(t, key, float(val))
 
    return ok(t.to_dict())
 
 
@app.route("/api/teams/reset", methods=["POST"])
def reset_teams():
    """Reload all teams from teams.json and clear the active season."""
    state.reset_teams()
    return ok(message="Teams reset to defaults and active season cleared.")
 
 
# Season
@app.route("/api/season/new", methods=["POST"])
def new_season():
    """Start a new season. Body: {year?, seed?}"""
    body = request.get_json(force=True, silent=True) or {}
    year = int(body.get("year", 2024))
    seed = body.get("seed")
    state.new_season(year=year, seed=seed)
    return ok({
        "season": year,
        "weeks": 18,
        "total_games": len(state.season_engine.schedule),
        "byes": state.season_engine.byes,
    })
 
 
@app.route("/api/season/schedule", methods=["GET"])
def get_schedule():
    """Return full regular season schedule, optionally filtered by week."""
    season_error = require_season()
    if season_error:
        return season_error
    week = request.args.get("week", type=int)
    games = state.season_engine.schedule
    if week is not None:
        games = [g for g in games if g.week == week]
    return ok([g.to_dict() for g in games])
 
 
@app.route("/api/season/week/<int:week>", methods=["POST"])
def simulate_week(week: int):
    """Simulate all games in a specific week."""
    season_error = require_season()
    if season_error:
        return season_error
    if week < 1 or week > 18:
        return err("Week must be 1-18.")
    results = state.season_engine.simulate_week(week)
    return ok({
        "week": week,
        "games_simulated": len(results),
        "games": [g.to_dict() for g in results],
    })


@app.route("/api/season/week/next", methods=["POST"])
def simulate_next_week():
    """Simulate the next week that still has unplayed games."""
    season_error = require_season()
    if season_error:
        return season_error

    next_week = state.season_engine.next_unsimulated_week()
    if next_week is None:
        return err("Regular season is already complete.", 409)

    results = state.season_engine.simulate_week(next_week)
    return ok({
        "week": next_week,
        "games_simulated": len(results),
        "games": [g.to_dict() for g in results],
    })
 
 
@app.route("/api/season/simulate_all", methods=["POST"])
def simulate_full_season():
    """Simulate the entire regular season at once."""
    season_error = require_season()
    if season_error:
        return season_error
    state.season_engine.simulate_full_season()
    return ok({
        "season": state.season_year,
        "message": "Full regular season simulated.",
        "total_games": len(state.season_engine.schedule),
    })


@app.route("/api/season/simulate_everything", methods=["POST"])
def simulate_everything():
    """Simulate the regular season, playoffs, and crown a champion."""
    season_error = require_season()
    if season_error:
        return season_error

    se = state.season_engine
    se.simulate_full_season()
    bracket = se.build_playoff_bracket()
    playoff_results = []
    for round_name in ["wildcard", "divisional", "conference", "superbowl"]:
        playoff_results.append(se.simulate_playoff_round(round_name))

    return ok({
        "season": state.season_year,
        "regular_season_games": len(se.schedule),
        "bracket": bracket,
        "playoff_results": playoff_results,
        "champion": se.get_champion(),
    })
 
 
@app.route("/api/season/standings", methods=["GET"])
def get_standings():
    """Return division standings."""
    season_error = require_season()
    if season_error:
        return season_error
    return ok(state.season_engine.get_standings())
 
 
@app.route("/api/season/standings/<conference>", methods=["GET"])
def get_conference_standings(conference: str):
    """Return standings for AFC or NFC."""
    season_error = require_season()
    if season_error:
        return season_error
    conf = conference.upper()
    if conf not in ("AFC", "NFC"):
        return err("Conference must be AFC or NFC.")
    return ok(state.season_engine.get_conference_standings(conf))


@app.route("/api/season/stats", methods=["GET"])
def get_season_stats():
    """Return team stat leaderboards and power rankings."""
    season_error = require_season()
    if season_error:
        return season_error

    category = request.args.get("category")
    if category:
        try:
            return ok(state.season_engine.get_team_stat_rankings(category))
        except ValueError as exc:
            return err(str(exc))

    return ok({
        "power_rankings": state.season_engine.get_power_rankings(),
        "stat_rankings": state.season_engine.get_all_team_stat_rankings(),
    })
 
 
@app.route("/api/season/status", methods=["GET"])
def season_status():
    """Return current season progress."""
    if not state.season_engine:
        return ok({"active": False})
    se = state.season_engine
    completed = sum(1 for g in se.schedule if g.is_completed)
    total = len(se.schedule)
    return ok({
        "active": True,
        "season": state.season_year,
        "current_week": se.current_week,
        "next_unsimulated_week": se.next_unsimulated_week(),
        "regular_season_complete": se.regular_season_complete,
        "games_completed": completed,
        "games_total": total,
        "pct_complete": round(completed / total * 100, 1) if total else 0,
    })
 
 
# Individual Game Simulation 
@app.route("/api/game/simulate", methods=["POST"])
def simulate_single_game():
    body = request.get_json(force=True, silent=True) or {}
    home_abbr = body.get("home", "").upper()
    away_abbr = body.get("away", "").upper()
 
    if not home_abbr or not away_abbr:
        return err("Provide 'home' and 'away' team abbreviations.")
    if home_abbr not in state.teams:
        return err(f"Unknown home team '{home_abbr}'.")
    if away_abbr not in state.teams:
        return err(f"Unknown away team '{away_abbr}'.")
    if home_abbr == away_abbr:
        return err("Home and away teams must be different.")
 
    weather_str = body.get("weather", "Clear")
    try:
        weather = WeatherCondition(weather_str)
    except ValueError:
        return err(f"Invalid weather. Options: {[w.value for w in WeatherCondition]}")
 
    hfa = float(body.get("home_field_advantage", 3.0))
    neutral = bool(body.get("neutral_site", False))
 
    # Work on temporary copies so we don't dirty season state
    home = copy.deepcopy(state.teams[home_abbr])
    away = copy.deepcopy(state.teams[away_abbr])
 
    import uuid as _uuid
    game = Game(
        game_id=str(_uuid.uuid4()),
        week=0,
        home_team=home_abbr,
        away_team=away_abbr,
        season=state.season_year,
        weather=weather,
        home_field_advantage=hfa,
        neutral_site=neutral,
    )
 
    state.game_engine.simulate(game, home, away)
    return ok(game.to_dict())
 
# Playoffs 
@app.route("/api/playoffs/build", methods=["POST"])
def build_playoff_bracket():
    """Seed teams and build the initial playoff bracket (requires completed season)."""
    season_error = require_season()
    if season_error:
        return season_error
    if not state.season_engine.regular_season_complete:
        return err("Regular season must be complete before building playoffs.", 409)
    bracket = state.season_engine.build_playoff_bracket()
    seeds = state.season_engine.get_playoff_seeds()
    return ok({"bracket": bracket, "seeds": seeds})
 
 
@app.route("/api/playoffs/seeds", methods=["GET"])
def get_playoff_seeds():
    season_error = require_season()
    if season_error:
        return season_error
    return ok(state.season_engine.get_playoff_seeds())
 
 
@app.route("/api/playoffs/round/<round_name>", methods=["POST"])
def simulate_playoff_round(round_name: str):
    season_error = require_season()
    if season_error:
        return season_error
    valid = ["wildcard", "divisional", "conference", "superbowl"]
    if round_name not in valid:
        return err(f"Round must be one of: {valid}")
    try:
        results = state.season_engine.simulate_playoff_round(round_name)
    except ValueError as exc:
        return err(str(exc), 409)
    return ok(results)
 
 
@app.route("/api/playoffs/games", methods=["GET"])
def get_playoff_games():
    season_error = require_season()
    if season_error:
        return season_error
    return ok(state.season_engine.get_all_playoff_games())
 
 
@app.route("/api/playoffs/champion", methods=["GET"])
def get_champion():
    season_error = require_season()
    if season_error:
        return season_error
    champ = state.season_engine.get_champion()
    if not champ:
        return ok(None, message="Super Bowl not yet played.")
    return ok(champ)
 
 
# Health Check
@app.route("/api/health", methods=["GET"])
def health():
    return ok({"status": "ok", "version": "1.0.0"})
 
 
# Entry Point
if __name__ == "__main__":
    print("NFL Season Simulator API starting on http://localhost:5000")
    print("Available endpoints:")
    for rule in app.url_map.iter_rules():
        print(f"  {', '.join(rule.methods - {'HEAD','OPTIONS'}):8s} {rule.rule}")
    app.run(debug=True, port=5000)
 

