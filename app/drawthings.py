import os
import json
import logging
import base64
from typing import Optional, Dict, Any, List, Tuple
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("image-agent.drawthings")

DEFAULT_DRAWTHINGS_URL = os.getenv("DRAWTHINGS_URL", "http://127.0.0.1:7860").rstrip("/")

class DrawThingsClient:
    def __init__(self, base_url: str = DEFAULT_DRAWTHINGS_URL):
        self.base_url = base_url

    async def check_health(self) -> Tuple[bool, str]:
        """Checks if Draw Things HTTP API server is reachable and responding."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/sdapi/v1/options")
                if res.status_code == 200:
                    return True, "Draw Things API is online"
        except Exception:
            pass
        return False, "Draw Things не запущен. Открой Draw Things и включи API Server (HTTP :7860)."

    async def generate_txt2img(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int = 8,
        seed: int = -1,
        guidance_scale: float = 1.0,
        shift: float = 3.0,
        loras: Optional[List[Dict[str, Any]]] = None,
        timeout: float = 240.0
    ) -> List[bytes]:
        """Submits a single txt2img generation request to Draw Things API."""
        url = f"{self.base_url}/sdapi/v1/txt2img"
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": steps,
            "width": width,
            "height": height,
            "seed": seed,
            "guidance_scale": guidance_scale,
            "shift": shift,
            "loras": loras or []
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Draw Things error {res.status_code}: {res.text}")

            data = res.json()
            images_b64 = data.get("images", [])
            if not images_b64:
                raise RuntimeError("Draw Things returned an empty image list")

            decoded = []
            for b64_str in images_b64:
                decoded.append(base64.b64decode(b64_str))
            return decoded
