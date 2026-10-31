/* ==========================================================================
   1. STATE & CONSTANTS
   ========================================================================== */
const state = {
  teams: [],
  status: { active: false },
  schedule: [],
  standings: {},
  playoffs: [],
  champion: null,
  week: 1,
  conference: "AFC",
  stat: "power",
  statRows: [],
  selectedTeam: null,
  loading: false,
};

const playoffRounds = ["wildcard", "divisional", "conference", "superbowl"];

const RATING_FIELDS = [
  ["offensive_rating", "Offense"],
  ["defensive_rating", "Defense"],
  ["special_teams_rating", "Special Teams"],
  ["coaching_rating", "Coaching"],
  ["morale", "Morale"],
];


/* ==========================================================================
   2. DOM & FORMAT HELPERS
   ========================================================================== */
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  const entities = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  };
  return String(value ?? "").replace(/[&<>'"]/g, (char) => entities[char]);
}

function record(team) {
  return `${team.wins}-${team.losses}${team.ties ? `-${team.ties}` : ""}`;
}

function showNotice(message, isError = false) {
  const notice = $("#notice");
  notice.textContent = message;
  notice.hidden = false;
  notice.classList.toggle("error", isError);
}

function clearNotice() {
  $("#notice").hidden = true;
}

function setLoading(loading) {
  state.loading = loading;

  $$("button").forEach((button) => {
    const isFilter =
      button.classList.contains("conference-btn") ||
      button.classList.contains("stat-btn");
    if (!isFilter) button.disabled = loading;
  });

  renderControls();
}


/* ==========================================================================
   3. API
   ========================================================================== */
async function api(path, options = {}) {
  let response;

  try {
    response = await fetch(`/api${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch {
    throw new Error(
      "The Flask backend is not reachable. Start the app with start_backend.bat and refresh."
    );
  }

  const payload = await response.json().catch(() => ({}));

  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || `Request failed (${response.status}).`);
  }

  return payload.data ?? payload;
}


/* ==========================================================================
   4. DATA LOADING & ACTIONS
   ========================================================================== */
async function refreshAll() {
  const [teams, status] = await Promise.all([
    api("/teams"),
    api("/season/status"),
  ]);

  state.teams = teams;
  state.status = status;

  if (status.active) {
    const [schedule, standings, playoffs, champion] = await Promise.all([
      api("/season/schedule"),
      api("/season/standings"),
      api("/playoffs/games"),
      api("/playoffs/champion"),
    ]);

    state.schedule = schedule;
    state.standings = standings;
    state.playoffs = playoffs;
    state.champion = champion;

    if (status.next_unsimulated_week) {
      state.week = status.next_unsimulated_week;
    }

    await loadStatRows();
  } else {
    state.schedule = [];
    state.standings = {};
    state.playoffs = [];
    state.champion = null;
    state.statRows = [];
  }

  render();
}

async function loadStatRows() {
  if (state.stat === "power") {
    // Note: the first request's result is discarded (kept as in the original).
    await api("/season/stats?category=total_yards");
    const data = await api("/season/stats");
    state.statRows = data.power_rankings;
  } else {
    state.statRows = await api(`/season/stats?category=${state.stat}`);
  }
}

async function action(successMessage, callback) {
  setLoading(true);
  clearNotice();

  try {
    await callback();
    await refreshAll();
    showNotice(successMessage);
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    setLoading(false);
  }
}


/* ==========================================================================
   5. RENDERING: CONTROLS & SEASON
   ========================================================================== */
function render() {
  renderControls();
  renderSeason();
  renderStandings();
  renderPlayoffs();
  renderTeams();
  renderStats();
  renderTeamSelects();
}

function renderControls() {
  const { active, regular_season_complete: complete } = state.status;

  $("#season-status").textContent = active
    ? `${state.status.games_completed}/${state.status.games_total} games`
    : "No active season";

  $("#next-week-btn").disabled =
    state.loading || !active || !state.status.next_unsimulated_week;

  $("#regular-season-btn").disabled = state.loading || !active || complete;

  $("#build-playoffs-btn").disabled =
    state.loading || !complete || state.playoffs.length > 0;

  $$("[data-round]").forEach((button) => {
    const hasPendingGames = state.playoffs.some(
      (game) =>
        game.playoff_round === button.dataset.round &&
        game.status !== "completed"
    );
    button.disabled = state.loading || !hasPendingGames;
  });
}

function renderSeason() {
  $("#progress-value").textContent = `${state.status.pct_complete || 0}%`;
  $("#current-week-value").textContent = state.status.current_week || "-";
  $("#next-week-value").textContent =
    state.status.next_unsimulated_week || "Done";

  $("#week-slider").value = state.week;
  $("#week-label").textContent = state.week;

  const games = state.schedule.filter((game) => game.week === state.week);
  const emptyMessage = state.status.active
    ? "No games scheduled for this week."
    : "Create a season to see the schedule.";

  $("#schedule-list").innerHTML = games.length
    ? games.map(gameRow).join("")
    : `<p class="empty">${emptyMessage}</p>`;
}

function gameRow(game) {
  const completed = game.status === "completed";
  const score = completed
    ? `${game.away_score} - ${game.home_score}`
    : game.playoff_round || `Week ${game.week}`;

  return `
    <div class="game-row ${completed ? "done" : ""}">
      <div>
        <strong>${escapeHtml(game.away_team)}</strong>
        <span>at</span>
        <strong>${escapeHtml(game.home_team)}</strong>
      </div>
      <div class="score">${escapeHtml(score)}</div>
    </div>`;
}


/* ==========================================================================
   6. RENDERING: STANDINGS & PLAYOFFS
   ========================================================================== */
function renderStandings() {
  $$(".conference-btn").forEach((button) => {
    button.classList.toggle("active", button.dataset.conference === state.conference);
  });

  const teams = Object.entries(state.standings)
    .filter(([division]) => division.startsWith(state.conference))
    .flatMap(([, rows]) => rows)
    .sort(
      (a, b) =>
        b.win_pct - a.win_pct || b.point_differential - a.point_differential
    );

  $("#standings-table").innerHTML = teams.length
    ? teams.map(standingsRow).join("")
    : `<p class="empty">Create a season to view standings.</p>`;
}

function standingsRow(team) {
  const diff = `${team.point_differential > 0 ? "+" : ""}${team.point_differential}`;

  return `
    <button class="team-row" data-team="${team.abbreviation}">
      <span>${escapeHtml(team.abbreviation)}</span>
      <span>${record(team)}</span>
      <span>${diff}</span>
    </button>`;
}

function renderPlayoffs() {
  $("#champion-card").innerHTML = state.champion
    ? `<div class="champion">
         <strong>Champion</strong>
         <strong>${escapeHtml(state.champion.full_name)}</strong>
         <span>${record(state.champion)}</span>
       </div>`
    : "";

  const emptyMessage = state.status.regular_season_complete
    ? "Build the bracket or click Sim Full Year."
    : "Complete the season, then build the bracket.";

  $("#playoff-list").innerHTML = state.playoffs.length
    ? state.playoffs.map(gameRow).join("")
    : `<p class="empty">${emptyMessage}</p>`;
}


/* ==========================================================================
   7. RENDERING: TEAMS & MATCHUP SELECTS
   ========================================================================== */
function renderTeams() {
  $("#team-grid").innerHTML =
    state.teams
      .map(
        (team) => `
        <button class="team-card" data-team="${team.abbreviation}">
          <span>${escapeHtml(team.abbreviation)}</span>
          <strong>${escapeHtml(team.full_name)}</strong>
          <small>${Math.round(team.overall_rating)} OVR</small>
        </button>`
      )
      .join("") || `<p class="empty">No teams available.</p>`;
}

function renderTeamSelects() {
  const selects = [$("#away-team"), $("#home-team")];
  const previous = selects.map((select) => select.value);

  const options = state.teams
    .map(
      (team) =>
        `<option value="${team.abbreviation}">${team.abbreviation} - ${escapeHtml(team.full_name)}</option>`
    )
    .join("");

  selects.forEach((select, index) => {
    const keepPrevious =
      previous[index] &&
      state.teams.some((team) => team.abbreviation === previous[index]);

    select.innerHTML = options;
    select.value = keepPrevious ? previous[index] : index ? "KC" : "SF";
  });
}


/* ==========================================================================
   8. RENDERING: STATS TABLE
   ========================================================================== */
function statTotal(team) {
  if (state.stat === "power") return record(team);
  if (state.stat === "yards_per_game") return team.yards_per_game.toFixed(1);
  return Number(team[state.stat] || 0).toLocaleString();
}

function statAverage(team) {
  if (state.stat === "power") return `${(team.win_pct * 100).toFixed(1)}%`;
  if (state.stat === "yards_per_game") {
    return Number(team.total_yards || 0).toLocaleString();
  }

  const games = team.games_played || 1;
  return (Number(team[state.stat] || 0) / games).toFixed(1);
}

function renderStats() {
  $$(".stat-btn").forEach((button) => {
    button.classList.toggle("active", button.dataset.stat === state.stat);
  });

  const rows = state.statRows;

  if (!rows.length) {
    $("#stats-table").innerHTML =
      `<p class="empty">Simulate games to populate team stat leaderboards.</p>`;
    return;
  }

  const header = `
    <div class="stats-header">
      <span>Rank</span>
      <span>Team</span>
      <span>Total</span>
      <span>Per Game</span>
      <span>Record</span>
    </div>`;

  const body = rows
    .map(
      (team) => `
      <button class="stats-row" data-team="${team.abbreviation}">
        <span class="rank">${team.rank}</span>
        <span class="team-name">
          <strong>${team.abbreviation}</strong>
          <small>${escapeHtml(team.full_name)}</small>
        </span>
        <span>${statTotal(team)}</span>
        <span>${statAverage(team)}</span>
        <span>${record(team)}</span>
      </button>`
    )
    .join("");

  $("#stats-table").innerHTML = header + body;
}


/* ==========================================================================
   9. TEAM DIALOG
   ========================================================================== */
function summaryItem(label, value) {
  return `<div><span>${label}</span><strong>${value}</strong></div>`;
}

function showTeam(abbreviation) {
  const team =
    state.teams.find((item) => item.abbreviation === abbreviation) ||
    Object.values(state.standings)
      .flat()
      .find((item) => item.abbreviation === abbreviation);

  if (!team) return;

  state.selectedTeam = team;
  $("#dialog-abbr").textContent = team.abbreviation;
  $("#dialog-title").textContent = team.full_name;

  // Rating sliders
  $("#rating-fields").innerHTML = RATING_FIELDS.map(
    ([key, label]) => `
      <label class="rating-field">${label}
        <input type="range" min="40" max="99" name="${key}" value="${Math.round(team[key])}">
        <span>${Math.round(team[key])}</span>
      </label>`
  ).join("");

  $$("#rating-fields input").forEach((input) => {
    input.addEventListener("input", () => {
      input.nextElementSibling.textContent = input.value;
    });
  });

  // Season summary
  $("#team-summary").innerHTML = team.games_played
    ? `<p class="eyebrow">Season Stats</p>
       <div class="summary-grid">
         ${summaryItem("Record", record(team))}
         ${summaryItem("Pass Yds", Number(team.passing_yards || 0).toLocaleString())}
         ${summaryItem("Rush Yds", Number(team.rushing_yards || 0).toLocaleString())}
         ${summaryItem("Total Yds", Number(team.total_yards || 0).toLocaleString())}
         ${summaryItem("TDs", team.touchdowns || 0)}
         ${summaryItem("INTs", team.interceptions || 0)}
       </div>`
    : `<p class="muted">No games played yet.</p>`;

  $("#team-dialog").showModal();
}


/* ==========================================================================
   10. EVENT LISTENERS
   ========================================================================== */

/* --- Season controls --- */
const newSeason = () =>
  api("/season/new", {
    method: "POST",
    body: JSON.stringify({ year: 2024, seed: Date.now() }),
  });

$("#new-season-btn").addEventListener("click", () =>
  action("New season created.", newSeason)
);

$("#next-week-btn").addEventListener("click", () =>
  action("Next week simulated.", async () => {
    const result = await api("/season/week/next", { method: "POST" });
    if (result.week === 18) {
      await api("/playoffs/build", { method: "POST" }).catch(() => null);
    }
  })
);

$("#regular-season-btn").addEventListener("click", () =>
  action("Regular season simulated and playoffs built.", async () => {
    await api("/season/simulate_all", { method: "POST" });
    await api("/playoffs/build", { method: "POST" });
  })
);

$("#full-year-btn").addEventListener("click", () =>
  action("Full NFL year simulated.", async () => {
    if (!state.status.active) await newSeason();
    await api("/season/simulate_everything", { method: "POST" });
  })
);

$("#build-playoffs-btn").addEventListener("click", () =>
  action("Playoff bracket built.", () =>
    api("/playoffs/build", { method: "POST" })
  )
);

$("#reset-btn").addEventListener("click", () =>
  action("Teams reset and active season cleared.", () =>
    api("/teams/reset", { method: "POST" })
  )
);

/* --- Schedule slider --- */
$("#week-slider").addEventListener("input", (event) => {
  state.week = Number(event.target.value);
  renderSeason();
});

/* --- Standings & stats filters --- */
$$(".conference-btn").forEach((button) => {
  button.addEventListener("click", () => {
    state.conference = button.dataset.conference;
    renderStandings();
  });
});

$$(".stat-btn").forEach((button) => {
  button.addEventListener("click", async () => {
    state.stat = button.dataset.stat;
    try {
      await loadStatRows();
      renderStats();
    } catch (error) {
      showNotice(error.message, true);
    }
  });
});

/* --- Playoff rounds --- */
$$("[data-round]").forEach((button) => {
  button.addEventListener("click", () =>
    action(`${button.dataset.round} round simulated.`, () =>
      api(`/playoffs/round/${button.dataset.round}`, { method: "POST" })
    )
  );
});

/* --- Team dialog (open on any [data-team] click) --- */
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-team]");
  if (target) showTeam(target.dataset.team);
});

$("#save-team-btn").addEventListener("click", () =>
  action("Team ratings updated.", async () => {
    const patch = Object.fromEntries(
      $$("#rating-fields input").map((input) => [input.name, Number(input.value)])
    );

    await api(`/teams/${state.selectedTeam.abbreviation}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });

    $("#team-dialog").close();
  })
);

/* --- Single game form --- */
$("#single-game-form").addEventListener("submit", (event) => {
  event.preventDefault();

  const home = $("#home-team").value;
  const away = $("#away-team").value;

  if (home === away) {
    showNotice("Choose two different teams.", true);
    return;
  }

  action("Game simulated.", async () => {
    const game = await api("/game/simulate", {
      method: "POST",
      body: JSON.stringify({ home, away, weather: $("#weather").value }),
    });

    $("#single-game-result").innerHTML = gameRow(game);
  });
});


/* ==========================================================================
   11. INIT
   ========================================================================== */
refreshAll().catch((error) => showNotice(error.message, true));