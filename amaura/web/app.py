"""
FastAPI Dashboard & Real-Time Discovery WebSocket Server
"""

import asyncio
import json
import os
from typing import Set, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from amaura.config import DiscoveryConfig
from amaura.engine.discovery import DiscoveryEngine


app = FastAPI(title="Amaura Discovery Engine Dashboard", version="0.1.0")

# Shared state for live monitoring
ACTIVE_ENGINE: Optional[DiscoveryEngine] = None
CONNECTED_WEBSOCKETS: Set[WebSocket] = set()
LATEST_STATE: Dict[str, Any] = {
    "is_running": False,
    "problem": "bin_packing",
    "generation": 0,
    "max_generations": 50,
    "best_fitness": None,
    "baseline_fitness": None,
    "improvement_pct": 0.0,
    "history": [],
    "best_candidate": None,
    "human_baseline": None
}


async def broadcast_telemetry(data: Dict[str, Any]):
    """Broadcast real-time evolution updates to all connected web dashboards."""
    dead_sockets = set()
    message = json.dumps(data)
    for ws in CONNECTED_WEBSOCKETS:
        try:
            await ws.send_text(message)
        except Exception:
            dead_sockets.add(ws)
    for dead in dead_sockets:
        CONNECTED_WEBSOCKETS.discard(dead)


def background_discovery_worker(config: DiscoveryConfig):
    """Run discovery engine in thread and stream updates."""
    global ACTIVE_ENGINE, LATEST_STATE
    LATEST_STATE["is_running"] = True
    LATEST_STATE["problem"] = config.problem
    LATEST_STATE["max_generations"] = config.generations
    LATEST_STATE["history"] = []

    engine = DiscoveryEngine(config)
    ACTIVE_ENGINE = engine

    def telemetry_handler(event: Dict[str, Any]):
        if event["type"] == "initialized":
            LATEST_STATE["human_baseline"] = event.get("human_baseline")
            if event.get("human_baseline"):
                LATEST_STATE["baseline_fitness"] = event["human_baseline"]["fitness"]
        elif event["type"] == "generation_step":
            summary = event["summary"]
            LATEST_STATE["generation"] = summary["generation"]
            LATEST_STATE["best_fitness"] = summary["best_fitness"]
            LATEST_STATE["improvement_pct"] = summary["improvement_pct"]
            LATEST_STATE["history"].append(summary)
            LATEST_STATE["best_candidate"] = event.get("best_candidate")

        # Put message in async event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_telemetry(event), loop)
        except Exception:
            pass

    engine.add_telemetry_callback(telemetry_handler)
    try:
        engine.run()
    finally:
        LATEST_STATE["is_running"] = False
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    broadcast_telemetry({"type": "finished", "state": LATEST_STATE}), loop
                )
        except Exception:
            pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    CONNECTED_WEBSOCKETS.add(websocket)
    try:
        # Send current state immediately on connect
        await websocket.send_text(json.dumps({"type": "state_sync", "state": LATEST_STATE}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        CONNECTED_WEBSOCKETS.discard(websocket)


@app.get("/api/state")
def get_state():
    return JSONResponse(content=LATEST_STATE)


@app.post("/api/start")
def start_discovery(problem: str = "bin_packing", generations: int = 40):
    global LATEST_STATE
    if LATEST_STATE["is_running"]:
        return JSONResponse(status_code=400, content={"error": "Engine is already actively running."})

    import threading
    config = DiscoveryConfig(
        problem=problem,
        generations=generations,
        num_islands=3,
        population_size=12
    )
    thread = threading.Thread(target=background_discovery_worker, args=(config,), daemon=True)
    thread.start()
    return JSONResponse(content={"status": "started", "problem": problem, "generations": generations})


@app.get("/", response_class=HTMLResponse)
def get_dashboard_html():
    static_html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_html_path):
        with open(static_html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Amaura Discovery Engine Web Dashboard</h1>"
