"""Local operator launcher. Does not print bootstrap/session credentials."""

import os, sys, time, subprocess, urllib.request, webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
RUNTIME.mkdir(exist_ok=True)
url = "http://127.0.0.1:8000/"


def running():
    try:
        with urllib.request.urlopen(url + "api/health", timeout=2) as r:
            return b"VERDICT" in r.read()
    except Exception:
        return False


if not running():
    python = (
        ROOT / "backend/.venv/Scripts/python.exe"
        if os.name == "nt"
        else ROOT / "backend/.venv/bin/python"
    )
    if not python.exists() or not (ROOT / "frontend/dist/index.html").exists():
        print("Install backend requirements and build frontend first. See README.md.")
        sys.exit(1)
    env = {
        **os.environ,
        "VERDICT_LOCAL_BOOTSTRAP": "true",
        "VERDICT_SUPABASE_MIRROR": "true",
    }
    with (RUNTIME / "server.log").open("ab") as log:
        subprocess.Popen(
            [
                str(python),
                "-m",
                "uvicorn",
                "app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
            ],
            cwd=ROOT / "backend",
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    for _ in range(50):
        if running():
            break
        time.sleep(0.2)
    else:
        print("Server did not start. Inspect runtime/server.log locally.")
        sys.exit(1)
access = RUNTIME / "local-access.url"
webbrowser.open(access.read_text().strip() if access.exists() else url)
print("VERDICT opened on localhost. Sandbox writes remain disabled by default.")
