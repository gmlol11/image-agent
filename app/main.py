import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .bonsai import BonsaiClient
from .drawthings import DrawThingsClient
from .storage import StorageManager
from .planner import ImagePlanner
from .runner import TaskManager
from .presets import load_presets

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("image-agent")

# Initialize modules
bonsai_client = BonsaiClient()
drawthings_client = DrawThingsClient()
storage_manager = StorageManager()
planner = ImagePlanner(bonsai_client=bonsai_client)
task_manager = TaskManager(planner=planner, drawthings=drawthings_client, storage=storage_manager)

app = FastAPI(title="Image Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schemas
class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Natural language prompt")
    format: str = Field("auto", description="auto | square | vertical | horizontal")
    quality: str = Field("draft", description="draft | final")
    count: int = Field(4, description="Number of variants to generate")
    advanced: Optional[Dict[str, Any]] = Field(default_factory=dict)

class RemixRequest(BaseModel):
    action: str = Field(..., description="similar | more | improve")
    task_id: str
    seed: Optional[int] = None

# API Endpoints
@app.get("/api/health")
async def get_health():
    dt_ok, dt_msg = await drawthings_client.check_health()
    bs_ok, bs_url = await bonsai_client.check_health()

    return {
        "drawthings": {
            "online": dt_ok,
            "message": dt_msg
        },
        "bonsai": {
            "online": bs_ok,
            "url": bs_url if bs_ok else None,
            "mode": "Bonsai 2 (Planning Layer)" if bs_ok else "Simple Mode (Fallback)"
        }
    }

@app.get("/api/presets")
async def get_presets():
    return load_presets()

@app.post("/api/generate")
async def generate_images(req: GenerateRequest):
    clean_prompt = req.prompt.strip()
    if not clean_prompt:
        raise HTTPException(status_code=400, detail="Промпт не может быть пустым")

    # Safety check on count: limit to 1..4 on 16GB Mac
    count = max(1, min(4, req.count))

    task_id = await task_manager.create_and_run(
        user_prompt=clean_prompt,
        format_choice=req.format,
        quality_choice=req.quality,
        advanced_overrides=req.advanced,
        count=count
    )

    return {"task_id": task_id, "status": "pending"}

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        # Check if it was in history
        record = storage_manager.get_record(task_id)
        if record:
            return {
                "task_id": task_id,
                "status": "completed",
                "progress": 1.0,
                "current_step_text": "Завершено",
                "plan": {
                    "prompt": record.get("prepared_prompt"),
                    "negative_prompt": record.get("negative_prompt"),
                    "profile": record.get("profile"),
                    "orientation": record.get("orientation"),
                    "width": record.get("width"),
                    "height": record.get("height"),
                    "steps": record.get("steps"),
                    "loras": record.get("loras")
                },
                "images": record.get("images", []),
                "duration_seconds": record.get("duration_seconds", 0)
            }
        raise HTTPException(status_code=404, detail="Task not found")

    return task.to_dict()

@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    cancelled = task_manager.cancel_task(task_id)
    return {"task_id": task_id, "cancelled": cancelled}

@app.post("/api/remix")
async def remix_image(req: RemixRequest):
    record = storage_manager.get_record(req.task_id)
    task = task_manager.get_task(req.task_id)
    base_data = task.to_dict() if task else record

    if not base_data:
        raise HTTPException(status_code=404, detail="Parent task not found")

    user_prompt = base_data.get("user_prompt", "")
    plan = base_data.get("plan", {}) or {}

    format_choice = plan.get("orientation", "auto")
    quality_choice = "final" if req.action == "improve" else "draft"
    count = 4 if req.action == "more" else 1

    advanced = {
        "prepared_prompt": plan.get("prompt"),
        "negative_prompt": plan.get("negative_prompt"),
        "seed": (req.seed + 1) if (req.seed is not None and req.action == "similar") else -1
    }

    new_task_id = await task_manager.create_and_run(
        user_prompt=user_prompt,
        format_choice=format_choice,
        quality_choice=quality_choice,
        advanced_overrides=advanced,
        count=count
    )

    return {"task_id": new_task_id, "action": req.action}

@app.get("/api/history")
async def get_history():
    return storage_manager.get_history()

@app.get("/api/outputs/{filename}")
async def get_output_file(filename: str):
    filepath = os.path.join(storage_manager.outputs_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath, media_type="image/png")

# Mount Web UI static directory
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
