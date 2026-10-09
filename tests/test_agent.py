import asyncio
import os
import sys

# Add image-agent root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.presets import load_presets, get_resolution, get_lora_list, get_negative_prompt
from app.drawthings import DrawThingsClient
from app.bonsai import BonsaiClient
from app.planner import ImagePlanner
from app.storage import StorageManager

async def test_all():
    print("=== 1. TESTING PRESETS ===")
    presets = load_presets()
    assert "profiles" in presets, "Presets must have profiles"
    print("✅ Presets loaded successfully")

    w, h = get_resolution("vertical", "draft")
    assert (w, h) == (768, 1152), f"Expected 768x1152, got {w}x{h}"
    print(f"✅ Resolution for draft vertical: {w}x{h}")

    loras = get_lora_list("realistic")
    assert len(loras) == 1 and loras[0]["model"] == "z_image_turbo_realism.safetensors", "Realism LoRA failed"
    print(f"✅ Realistic LoRA: {loras}")

    neg = get_negative_prompt("base", is_product=True)
    assert "text" in neg and "typography" in neg, "Product anti-text negative prompt missing"
    print("✅ Product anti-text negative prompt verified")

    print("\n=== 2. TESTING SERVICE HEALTH ===")
    dt_client = DrawThingsClient()
    dt_ok, dt_msg = await dt_client.check_health()
    print(f"Draw Things health: {dt_ok} ({dt_msg})")
    assert dt_ok, "Draw Things must be online"

    bonsai_client = BonsaiClient()
    bs_ok, bs_msg = await bonsai_client.check_health()
    print(f"Bonsai health: {bs_ok} ({bs_msg})")

    print("\n=== 3. TESTING PLANNER (SCENARIOS & HEURISTICS) ===")
    planner = ImagePlanner(bonsai_client=bonsai_client)

    # Scenario 1: Knight under rain
    p1 = "Сделай кинематографичную фотографию средневекового рыцаря в тяжёлых доспехах, стоящего под дождём у разрушенного замка. Мрачная атмосфера, вечер."
    plan1 = await planner.plan(p1)
    print("Scenario 1 (Knight):", plan1["intent"], plan1["orientation"], f"{plan1['width']}x{plan1['height']}")
    assert plan1["orientation"] == "horizontal", f"Expected horizontal, got {plan1['orientation']}"
    assert "knight" in plan1["prompt"].lower() or "рыцар" in plan1["prompt"].lower(), "Prompt subject altered"

    # Scenario 2: Full body fashion model on stone stairs
    p2 = "Сделай реалистичную fashion-фотографию взрослой модели в полный рост на широкой каменной лестнице."
    plan2 = await planner.plan(p2)
    print("Scenario 2 (Model):", plan2["intent"], plan2["orientation"], f"{plan2['width']}x{plan2['height']}", plan2["lora_weights"])
    assert plan2["orientation"] == "vertical", f"Expected vertical, got {plan2['orientation']}"
    assert plan2["width"] == 768 and plan2["height"] == 1152, "Expected 768x1152"
    assert plan2["lora_weights"]["realism"] >= 0.5, "Expected realism LoRA active"
    assert "head to toe" in plan2["prompt"].lower() or "full body" in plan2["prompt"].lower()

    # Scenario 3: Product perfume bottle without text
    p3 = "Сделай премиальную рекламную фотографию матового чёрного флакона духов на мокром камне. Без логотипов и надписей."
    plan3 = await planner.plan(p3)
    print("Scenario 3 (Product):", plan3["intent"], plan3["orientation"], f"{plan3['width']}x{plan3['height']}")
    assert plan3["orientation"] == "square", f"Expected square, got {plan3['orientation']}"
    assert "unbranded" in plan3["prompt"].lower() or "no logo" in plan3["prompt"].lower()
    assert "text" in plan3["negative_prompt"].lower()

    # Scenario 4: Unrestricted artistic nude
    p4 = "Художественная эстетичная фотография девушки в спальне в мягком утреннем свете."
    plan4 = await planner.plan(p4)
    print("Scenario 4 (Unrestricted/Sensual):", plan4["intent"], plan4["profile"], plan4["lora_weights"], f"is_unrestricted={plan4['is_unrestricted']}")
    assert plan4["is_unrestricted"] or plan4["lora_weights"]["realism"] > 0, "Expected realism/unrestricted adapter"
    
    # Scenario 4b: Explicit nude age verification
    p4b = "эротическая фотография в спальне, обнаженная натура"
    plan4b = await planner.plan(p4b)
    print("Scenario 4b (Explicit Age Safety):", plan4b["prompt"][:80])
    assert "25+" in plan4b["prompt"] or "mature" in plan4b["prompt"], "Expected explicit adult 25+ age restriction"

    print("\n=== 4. TESTING INFERENCE INTEGRATION (1 REAL IMAGE GENERATION) ===")
    print("Generating 1 test image through planner plan...")
    storage = StorageManager()
    img_bytes = await dt_client.generate_txt2img(
        prompt=plan3["prompt"],
        negative_prompt=plan3["negative_prompt"],
        width=768,
        height=768,
        steps=8,
        seed=4242
    )
    saved = storage.save_image("unit_test", 1, img_bytes[0], 4242)
    print(f"✅ Generated and saved test image: {saved['filepath']} ({saved['size_kb']} KB)")
    assert os.path.exists(saved["filepath"]), "Saved image file must exist"

    print("\n🎉 ALL UNIT AND INTEGRATION TESTS PASSED SUCCESSFULLY! 🎉")

if __name__ == "__main__":
    asyncio.run(test_all())
