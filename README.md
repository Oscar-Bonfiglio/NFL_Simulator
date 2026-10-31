# NFL Sim

Interactive NFL-style season simulator built with Flask, HTML, CSS, and plain JavaScript.

## Backend

```powershell
pip install -r requirements.txt
python main.py
```

The app and API run at `http://localhost:5000`. Open that address in your browser after starting the backend.

On Windows you can also double-click `start_backend.bat`.

Useful endpoints:

- `GET /api/health`
- `GET /api/meta`
- `POST /api/season/new`
- `POST /api/season/week/next`
- `POST /api/season/simulate_all`
- `POST /api/season/simulate_everything`
- `GET /api/season/schedule`
- `GET /api/season/standings`
- `POST /api/playoffs/build`
- `POST /api/playoffs/round/<round_name>`
- `GET /api/playoffs/champion`

## Interface

The interactive interface lives in `static/` and is served by Flask. There is no React, Node, npm, or separate frontend server to run.

Open `http://localhost:5000` after running the backend.

See `ABOUT.md` to personalize the creator information shown in the interface.
