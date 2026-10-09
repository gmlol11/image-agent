import os
import re
import logging
from typing import Dict, Any, Optional
from .presets import (
    load_presets,
    get_resolution,
    get_lora_list,
    get_negative_prompt
)
from .bonsai import BonsaiClient

logger = logging.getLogger("image-agent.planner")

PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "image_planner.txt")

class ImagePlanner:
    def __init__(self, bonsai_client: Optional[BonsaiClient] = None):
        self.bonsai = bonsai_client or BonsaiClient()
        self.system_prompt = self._load_system_prompt()
        self.presets = load_presets()

    def _load_system_prompt(self) -> str:
        if os.path.exists(PROMPT_FILE):
            try:
                with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return "You are an AI image planner. Return strictly valid JSON."

    async def plan(
        self,
        user_prompt: str,
        format_choice: str = "auto",
        quality_choice: str = "draft",
        advanced_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates planning: tries Bonsai 2 first, falls back to rule-based Simple Mode.
        Enforces age safety, format constraints, and user overrides.
        """
        advanced_overrides = advanced_overrides or {}
        raw_plan = None
        planner_source = "bonsai"

        # 1. Try Bonsai LLM
        try:
            raw_plan = await self.bonsai.plan_image(self.system_prompt, user_prompt)
        except Exception as e:
            logger.warning(f"Bonsai query error: {e}")

        # 2. Fallback to Simple Mode if Bonsai failed or returned invalid data
        if not raw_plan or not isinstance(raw_plan, dict) or "prompt" not in raw_plan:
            logger.info("Executing heuristic Simple Mode planner fallback")
            raw_plan = self._simple_mode_plan(user_prompt)
            planner_source = "simple_mode"

        # 3. Age safety check
        intent = raw_plan.get("intent", "other").lower()
        profile = raw_plan.get("profile", "base").lower()
        production_prompt = raw_plan.get("prompt", user_prompt)

        is_nude_or_sexualized = any(
            w in user_prompt.lower() or w in production_prompt.lower()
            for w in ["nude", "naked", "boudoir", "эроти", "обнажен", "ню", "sensual", "intimate"]
        )

        if is_nude_or_sexualized or "unrestricted" in profile or intent == "unrestricted":
            if "25+" not in production_prompt.lower():
                production_prompt = f"adult 25+ fictional character, {production_prompt}"

        # 4. Resolve Orientation
        chosen_orientation = raw_plan.get("orientation", "vertical").lower()
        fmt = format_choice.lower().strip()
        if fmt in ("square", "vertical", "horizontal"):
            chosen_orientation = fmt
        elif chosen_orientation not in ("square", "vertical", "horizontal"):
            chosen_orientation = "vertical"

        # 5. Resolve Resolution
        width, height = get_resolution(chosen_orientation, quality_choice)

        # 6. Resolve Profile and LoRA weights
        loras_dict = raw_plan.get("loras", {})
        realism_weight = float(loras_dict.get("realism", 0.0))
        unrestricted_weight = float(loras_dict.get("unrestricted", 0.0))

        if "unrestricted" in profile:
            if unrestricted_weight == 0:
                unrestricted_weight = 0.85
            if "realistic" in profile and realism_weight == 0:
                realism_weight = 0.60
        elif profile == "realistic" and realism_weight == 0:
            realism_weight = 0.60

        # Check product text suppression
        is_product = intent in ("product", "advertising") or "product" in user_prompt.lower() or "флакон" in user_prompt.lower()
        if is_product:
            if "logo" not in user_prompt.lower() and "надпис" not in user_prompt.lower():
                if not any(w in production_prompt.lower() for w in ["unbranded", "no logo", "no text"]):
                    production_prompt = f"commercial product photography of a clean unbranded object, no visible logo, clean smooth surface, {production_prompt}"

        negative_prompt = raw_plan.get("negative_prompt", "")
        if not negative_prompt:
            negative_prompt = get_negative_prompt(profile, is_product=is_product)
        elif is_product and "text" not in negative_prompt:
            negative_prompt = f"{negative_prompt}, {self.presets.get('negative_prompts', {}).get('product_anti_text', '')}"

        # 7. Apply Advanced Overrides
        if advanced_overrides.get("prepared_prompt"):
            production_prompt = advanced_overrides["prepared_prompt"].strip()
        if advanced_overrides.get("negative_prompt"):
            negative_prompt = advanced_overrides["negative_prompt"].strip()
        if advanced_overrides.get("width"):
            width = int(advanced_overrides["width"])
        if advanced_overrides.get("height"):
            height = int(advanced_overrides["height"])
        if "realism_lora" in advanced_overrides:
            realism_weight = float(advanced_overrides["realism_lora"])
        if "unrestricted_lora" in advanced_overrides:
            unrestricted_weight = float(advanced_overrides["unrestricted_lora"])

        steps = int(advanced_overrides.get("steps") or self.presets.get("engine_defaults", {}).get("steps", 8))
        seed = int(advanced_overrides.get("seed", -1))

        # Format LoRA list for Draw Things API
        active_loras = get_lora_list(
            profile,
            loras_override={"realism": realism_weight, "unrestricted": unrestricted_weight}
        )

        is_unrestricted = unrestricted_weight > 0 or "unrestricted" in profile

        return {
            "intent": intent,
            "profile": profile,
            "prompt": production_prompt,
            "negative_prompt": negative_prompt,
            "orientation": chosen_orientation,
            "width": width,
            "height": height,
            "steps": steps,
            "seed": seed,
            "loras": active_loras,
            "lora_weights": {
                "realism": round(realism_weight, 2),
                "unrestricted": round(unrestricted_weight, 2)
            },
            "is_unrestricted": is_unrestricted,
            "planner_source": planner_source,
            "reason": raw_plan.get("reason", "Automatic classification")
        }

    def _simple_mode_plan(self, user_prompt: str) -> Dict[str, Any]:
        """Heuristic rule-based fallback when Bonsai is offline."""
        p_lower = user_prompt.lower()

        # Intent detection
        if any(w in p_lower for w in ["полный рост", "во весь рост", "full body", "feet", "ноги", "head to toe", "ступн"]):
            intent = "full_body_person"
            profile = "realistic"
            orientation = "vertical"
            realism = 0.60
            unrestricted = 0.0
            expanded = f"{user_prompt}, full body shot, head to toe, feet visible on ground, subject fully inside frame, natural relaxed pose, architectural or natural background, golden hour lighting, authentic photography"
        elif any(w in p_lower for w in ["ню", "обнажен", "эроти", "голая", "голый", "nude", "naked", "boudoir", "sensual", "будуар", "интимн"]):
            intent = "unrestricted"
            profile = "unrestricted_realistic" if any(w in p_lower for w in ["фото", "реалистич", "photo", "realistic", "кадр", "съемк", "съёмк"]) else "unrestricted"
            orientation = "vertical"
            realism = 0.60 if profile == "unrestricted_realistic" else 0.0
            unrestricted = 0.85
            expanded = f"tasteful fine-art photography of a beautiful fictional 26yo adult woman, aesthetic nude, natural daylight, soft shadows, {user_prompt}"
        elif any(w in p_lower for w in ["портрет", "девушк", "женщин", "мужчин", "модел", "лиц", "глаз", "portrait", "face", "woman", "man", "model", "человек"]):
            intent = "portrait"
            profile = "realistic"
            orientation = "vertical"
            realism = 0.60
            unrestricted = 0.0
            expanded = f"cinematic portrait of {user_prompt}, natural skin texture, subtle lighting, highly detailed eyes, 35mm f/1.8 lens, realistic photography, authentic look"
        elif any(w in p_lower for w in ["флакон", "дух", "бутылк", "предмет", "товар", "perfume", "bottle", "product", "commercial", "реклам", "часы"]):
            intent = "product"
            profile = "base"
            orientation = "square"
            realism = 0.0
            unrestricted = 0.0
            expanded = f"commercial product photography of a clean unbranded luxury object, {user_prompt}, pristine glass and surface, water droplets, soft volumetric lighting, moody dark stone background"
        elif any(w in p_lower for w in ["пейзаж", "замок", "рыцар", "лес", "гор", "кино", "кинематографич", "ночь", "дожд", "landscape", "knight", "cinematic", "rain"]):
            intent = "cinematic"
            profile = "base"
            orientation = "horizontal"
            realism = 0.0
            unrestricted = 0.0
            expanded = f"cinematic 35mm film still of {user_prompt}, atmospheric perspective, volumetric fog, moody lighting, wide angle composition, rich deep tones, masterpiece"
        elif any(w in p_lower for w in ["арт", "рисунок", "иллюстрац", "аниме", "anime", "illustration", "painting"]):
            intent = "illustration"
            profile = "base"
            orientation = "square"
            realism = 0.0
            unrestricted = 0.0
            expanded = f"detailed digital illustration of {user_prompt}, vibrant colors, artistic rendering, dynamic composition"
        else:
            intent = "other"
            profile = "base"
            orientation = "vertical"
            realism = 0.0
            unrestricted = 0.0
            expanded = f"{user_prompt}, high quality, beautiful composition, natural lighting, highly detailed"

        return {
            "intent": intent,
            "profile": profile,
            "prompt": expanded,
            "negative_prompt": "",
            "orientation": orientation,
            "loras": {
                "realism": realism,
                "unrestricted": unrestricted
            },
            "reason": f"Simple mode heuristic classification ({intent})"
        }
