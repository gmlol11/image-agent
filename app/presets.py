import json
import os
from typing import Dict, Any, Tuple

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "presets.json")

DEFAULT_PRESETS = {
    "profiles": {
        "base": {"name": "Base", "realism_lora": 0.0, "unrestricted_lora": 0.0},
        "realistic": {"name": "Realistic", "realism_lora": 0.60, "unrestricted_lora": 0.0},
        "unrestricted": {"name": "Unrestricted", "realism_lora": 0.0, "unrestricted_lora": 0.85},
        "unrestricted_realistic": {"name": "Unrestricted Realistic", "realism_lora": 0.60, "unrestricted_lora": 0.85},
        "unrestricted_explicit": {"name": "Unrestricted Explicit", "realism_lora": 0.0, "unrestricted_lora": 0.95}
    },
    "lora_files": {
        "realism": "z_image_turbo_realism.safetensors",
        "unrestricted": "z_image_turbo_nsfw.safetensors"
    },
    "resolutions": {
        "draft": {
            "square": {"width": 768, "height": 768},
            "vertical": {"width": 768, "height": 1152},
            "horizontal": {"width": 1152, "height": 768}
        },
        "final": {
            "square": {"width": 1024, "height": 1024},
            "vertical": {"width": 832, "height": 1216},
            "horizontal": {"width": 1216, "height": 832}
        }
    },
    "engine_defaults": {
        "steps": 8,
        "guidance_scale": 1.0,
        "shift": 3.0,
        "batch_count": 4
    },
    "negative_prompts": {
        "default": "ugly, deformed, noisy, blurry, distorted, low quality, bad anatomy",
        "realistic": "ugly, deformed, noisy, blurry, distorted, low quality, bad anatomy, plastic skin, doll, cartoon, 3d render, oversaturated, airbrushed",
        "product_anti_text": "text, typography, watermark, label, logo, letters, words, brand name, signature, writing, font, inscription, sticker, bad typography",
        "unrestricted": "ugly, deformed, noisy, blurry, distorted, low quality, bad anatomy, plastic skin, censor, blur, mosaic, bar, watermark"
    }
}

def load_presets() -> Dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_PRESETS

def get_resolution(orientation: str, quality: str) -> Tuple[int, int]:
    presets = load_presets()
    qual = "final" if quality.lower() in ("final", "high") else "draft"
    orient = orientation.lower()
    if orient not in ("square", "vertical", "horizontal"):
        orient = "vertical"
    res_map = presets.get("resolutions", {}).get(qual, {}).get(orient, {"width": 768, "height": 1152})
    return res_map["width"], res_map["height"]

def get_lora_list(profile: str, loras_override: Dict[str, float] = None) -> list:
    presets = load_presets()
    lora_files = presets.get("lora_files", {})
    profiles = presets.get("profiles", {})

    prof_data = profiles.get(profile, profiles.get("base", {}))
    realism_w = prof_data.get("realism_lora", 0.0)
    unrestricted_w = prof_data.get("unrestricted_lora", 0.0)

    if loras_override:
        if "realism" in loras_override:
            realism_w = float(loras_override["realism"])
        if "unrestricted" in loras_override:
            unrestricted_w = float(loras_override["unrestricted"])

    loras = []
    if unrestricted_w > 0 and "unrestricted" in lora_files:
        loras.append({"model": lora_files["unrestricted"], "weight": round(unrestricted_w, 2)})
    if realism_w > 0 and "realism" in lora_files:
        loras.append({"model": lora_files["realism"], "weight": round(realism_w, 2)})

    return loras

def get_negative_prompt(profile: str, is_product: bool = False, extra_negative: str = "") -> str:
    presets = load_presets()
    neg_dict = presets.get("negative_prompts", {})
    
    parts = []
    if "unrestricted" in profile:
        parts.append(neg_dict.get("unrestricted", neg_dict.get("default", "")))
    elif profile == "realistic":
        parts.append(neg_dict.get("realistic", neg_dict.get("default", "")))
    else:
        parts.append(neg_dict.get("default", ""))

    if is_product:
        parts.append(neg_dict.get("product_anti_text", ""))

    if extra_negative:
        parts.append(extra_negative)

    return ", ".join([p.strip() for p in parts if p.strip()])
