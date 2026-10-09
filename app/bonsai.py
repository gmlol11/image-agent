import os
import json
import logging
import re
from typing import Optional, Dict, Any, Tuple
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("image-agent.bonsai")

DEFAULT_BASE_URL = os.getenv("BONSAI_BASE_URL", "http://127.0.0.1:8080/v1")
AUTO_DISCOVER = os.getenv("AUTO_DISCOVER_BONSAI", "true").lower() in ("true", "1", "yes")

COMMON_PORTS = [8080, 8081, 11434, 1234]

class BonsaiClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.active_url = self.base_url

    async def check_health(self) -> Tuple[bool, str]:
        if await self._probe_url(self.active_url):
            return True, self.active_url

        if AUTO_DISCOVER:
            for port in COMMON_PORTS:
                candidate = f"http://127.0.0.1:{port}/v1"
                if candidate != self.active_url and await self._probe_url(candidate):
                    logger.info(f"Auto-discovered active Bonsai endpoint at {candidate}")
                    self.active_url = candidate
                    return True, candidate

        return False, "Bonsai server not reachable"

    async def _probe_url(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                root = url.replace("/v1", "")
                r_health = await client.get(f"{root}/health")
                if r_health.status_code == 200:
                    return True
                r_models = await client.get(f"{url}/models")
                if r_models.status_code == 200:
                    return True
        except Exception:
            pass
        return False

    async def plan_image(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        healthy, active_url = await self.check_health()
        if not healthy:
            logger.warning(f"Bonsai server offline at {self.active_url}")
            return None

        url = f"{active_url}/chat/completions"
        payload = {
            "model": "bonsai-2-27b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "top_p": 0.95,
            "max_tokens": 512,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}
        }

        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    logger.error(f"Bonsai returned status {res.status_code}: {res.text}")
                    return None
                data = res.json()
                raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if not raw_text:
                    return None

                # Clean markdown backticks
                clean_text = raw_text
                if "```json" in clean_text:
                    match = re.search(r"```json\s*(.*?)\s*```", clean_text, re.DOTALL)
                    if match:
                        clean_text = match.group(1).strip()
                elif "```" in clean_text:
                    match = re.search(r"```\s*(.*?)\s*```", clean_text, re.DOTALL)
                    if match:
                        clean_text = match.group(1).strip()

                # Extract JSON if surrounded by extraneous text
                if not clean_text.startswith("{"):
                    start = clean_text.find("{")
                    end = clean_text.rfind("}")
                    if start != -1 and end != -1:
                        clean_text = clean_text[start:end+1]

                return json.loads(clean_text)
        except Exception as e:
            logger.error(f"Failed to parse Bonsai planning response: {e}")
            return None
