import os
import json
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

DEFAULT_OUTPUTS_DIR = os.getenv("OUTPUTS_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs"))

class StorageManager:
    def __init__(self, outputs_dir: str = DEFAULT_OUTPUTS_DIR):
        self.outputs_dir = os.path.abspath(outputs_dir)
        os.makedirs(self.outputs_dir, exist_ok=True)
        self.history_file = os.path.join(self.outputs_dir, "history.json")
        self._init_history()

    def _init_history(self):
        if not os.path.exists(self.history_file):
            try:
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception:
                pass

    def save_image(self, task_id: str, index: int, image_bytes: bytes, seed: int) -> Dict[str, Any]:
        filename = f"{task_id}_{index}_{seed}.png"
        filepath = os.path.join(self.outputs_dir, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        size_kb = round(len(image_bytes) / 1024, 1)
        return {
            "filename": filename,
            "filepath": filepath,
            "url": f"/api/outputs/{filename}",
            "seed": seed,
            "size_kb": size_kb
        }

    def add_history_record(self, record: Dict[str, Any]):
        records = self.get_history()
        records.insert(0, record)
        # Keep latest 50 records
        records = records[:50]
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_history(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def get_record(self, task_id: str) -> Optional[Dict[str, Any]]:
        for r in self.get_history():
            if r.get("task_id") == task_id:
                return r
        return None
