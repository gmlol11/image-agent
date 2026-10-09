import asyncio
import time
import random
import uuid
import logging
from typing import Dict, Any, Optional, List
from .storage import StorageManager
from .drawthings import DrawThingsClient
from .planner import ImagePlanner

logger = logging.getLogger("image-agent.runner")

class TaskState:
    def __init__(self, task_id: str, user_prompt: str, count: int = 4):
        self.task_id = task_id
        self.user_prompt = user_prompt
        self.count = count
        self.status = "pending"  # pending, planning, generating, completed, cancelled, failed
        self.current_step_text = "В очереди..."
        self.current_index = 0
        self.total_count = count
        self.progress = 0.0
        self.plan: Optional[Dict[str, Any]] = None
        self.images: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        self.cancelled = False
        self.start_time = time.time()
        self.end_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        duration = round((self.end_time or time.time()) - self.start_time, 1)
        return {
            "task_id": self.task_id,
            "user_prompt": self.user_prompt,
            "status": self.status,
            "current_step_text": self.current_step_text,
            "current_index": self.current_index,
            "total_count": self.total_count,
            "progress": round(self.progress, 2),
            "plan": self.plan,
            "images": self.images,
            "error": self.error,
            "cancelled": self.cancelled,
            "duration_seconds": duration
        }

class TaskManager:
    def __init__(
        self,
        planner: ImagePlanner,
        drawthings: DrawThingsClient,
        storage: StorageManager
    ):
        self.planner = planner
        self.drawthings = drawthings
        self.storage = storage
        self.tasks: Dict[str, TaskState] = {}

    def get_task(self, task_id: str) -> Optional[TaskState]:
        return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task and task.status in ("pending", "planning", "generating"):
            task.cancelled = True
            task.status = "cancelled"
            task.current_step_text = "Генерация отменена пользователем"
            task.end_time = time.time()
            return True
        return False

    async def create_and_run(
        self,
        user_prompt: str,
        format_choice: str = "auto",
        quality_choice: str = "draft",
        advanced_overrides: Optional[Dict[str, Any]] = None,
        count: int = 4
    ) -> str:
        task_id = f"gen_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        task = TaskState(task_id, user_prompt, count=count)
        self.tasks[task_id] = task

        # Launch async worker in background
        asyncio.create_task(self._run_task(task, format_choice, quality_choice, advanced_overrides))
        return task_id

    async def _run_task(
        self,
        task: TaskState,
        format_choice: str,
        quality_choice: str,
        advanced_overrides: Optional[Dict[str, Any]]
    ):
        try:
            # 1. Health check Draw Things
            dt_ok, dt_msg = await self.drawthings.check_health()
            if not dt_ok:
                task.status = "failed"
                task.error = dt_msg
                task.current_step_text = dt_msg
                task.end_time = time.time()
                return

            # 2. Planning phase
            task.status = "planning"
            task.current_step_text = "Подготавливаю промпт..."
            plan = await self.planner.plan(
                user_prompt=task.user_prompt,
                format_choice=format_choice,
                quality_choice=quality_choice,
                advanced_overrides=advanced_overrides
            )
            task.plan = plan

            if task.cancelled:
                task.status = "cancelled"
                task.end_time = time.time()
                return

            # 3. Sequential Generation Loop
            task.status = "generating"
            base_seed = plan.get("seed", -1)

            for i in range(task.count):
                if task.cancelled:
                    break

                task.current_index = i + 1
                task.current_step_text = f"Генерирую {i + 1} из {task.count}..."
                task.progress = i / task.count

                # Resolve seed per iteration
                if base_seed == -1:
                    iter_seed = random.randint(1000, 999999)
                else:
                    iter_seed = base_seed + i

                # Call Draw Things API
                img_bytes_list = await self.drawthings.generate_txt2img(
                    prompt=plan["prompt"],
                    negative_prompt=plan["negative_prompt"],
                    width=plan["width"],
                    height=plan["height"],
                    steps=plan["steps"],
                    seed=iter_seed,
                    loras=plan.get("loras", [])
                )

                if task.cancelled:
                    break

                # Save generated image
                saved_info = self.storage.save_image(
                    task_id=task.task_id,
                    index=i + 1,
                    image_bytes=img_bytes_list[0],
                    seed=iter_seed
                )
                task.images.append(saved_info)
                task.current_step_text = f"Готово {i + 1} из {task.count}"
                task.progress = (i + 1) / task.count

            # Finalize
            task.end_time = time.time()
            if not task.cancelled:
                task.status = "completed"
                task.current_step_text = f"Готово! Сгенерировано {len(task.images)} изображений"

            # Record history
            history_record = {
                "task_id": task.task_id,
                "user_prompt": task.user_prompt,
                "prepared_prompt": plan.get("prompt"),
                "negative_prompt": plan.get("negative_prompt"),
                "profile": plan.get("profile"),
                "intent": plan.get("intent"),
                "orientation": plan.get("orientation"),
                "width": plan.get("width"),
                "height": plan.get("height"),
                "quality": quality_choice,
                "steps": plan.get("steps"),
                "loras": plan.get("loras"),
                "images": task.images,
                "duration_seconds": round(task.end_time - task.start_time, 1),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.storage.add_history_record(history_record)

        except Exception as e:
            logger.exception(f"Task {task.task_id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
            task.current_step_text = f"Ошибка генерации: {str(e)}"
            task.end_time = time.time()
