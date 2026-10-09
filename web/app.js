// Image Agent Frontend Logic
document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const dtStatus = document.getElementById("dtStatus");
  const bonsaiStatus = document.getElementById("bonsaiStatus");
  const serviceAlert = document.getElementById("serviceAlert");
  const alertTitle = document.getElementById("alertTitle");
  const alertDesc = document.getElementById("alertDesc");

  const promptInput = document.getElementById("promptInput");
  const formatSelector = document.getElementById("formatSelector");
  const qualitySelector = document.getElementById("qualitySelector");
  const generateBtn = document.getElementById("generateBtn");

  const advancedToggle = document.getElementById("advancedToggle");
  const advancedContent = document.getElementById("advancedContent");
  const advPreparedPrompt = document.getElementById("advPreparedPrompt");
  const advNegPrompt = document.getElementById("advNegPrompt");
  const advSeed = document.getElementById("advSeed");
  const advSteps = document.getElementById("advSteps");
  const advWidth = document.getElementById("advWidth");
  const advHeight = document.getElementById("advHeight");
  const advRealismLora = document.getElementById("advRealismLora");
  const advNsfwLora = document.getElementById("advNsfwLora");

  const progressSection = document.getElementById("progressSection");
  const progressText = document.getElementById("progressText");
  const progressBar = document.getElementById("progressBar");
  const unrestrictedBadge = document.getElementById("unrestrictedBadge");
  const cancelBtn = document.getElementById("cancelBtn");

  const resultsGrid = document.getElementById("resultsGrid");
  const resultsCount = document.getElementById("resultsCount");
  const detailsBtn = document.getElementById("detailsBtn");

  const detailsModal = document.getElementById("detailsModal");
  const closeDetailsModal = document.getElementById("closeDetailsModal");
  const detailsContent = document.getElementById("detailsContent");

  const historyBtn = document.getElementById("historyBtn");
  const historyDrawer = document.getElementById("historyDrawer");
  const closeHistoryBtn = document.getElementById("closeHistoryBtn");
  const historyList = document.getElementById("historyList");

  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightboxImg");
  const closeLightbox = document.getElementById("closeLightbox");

  // State
  let selectedFormat = "auto";
  let selectedQuality = "draft";
  let currentTaskId = null;
  let pollingInterval = null;
  let lastCompletedPlan = null;

  // 1. Health Checks
  async function checkHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("Health check failed");
      const data = await res.json();

      // Draw Things
      if (data.drawthings.online) {
        dtStatus.className = "status-pill online";
        dtStatus.innerHTML = '<span class="dot"></span> Draw Things: Готов';
        serviceAlert.classList.add("hidden");
      } else {
        dtStatus.className = "status-pill offline";
        dtStatus.innerHTML = '<span class="dot"></span> Draw Things: Офлайн';
        alertTitle.textContent = "Draw Things не запущен";
        alertDesc.textContent = "Открой Draw Things и включи API Server (HTTP :7860).";
        serviceAlert.classList.remove("hidden");
      }

      // Bonsai
      if (data.bonsai.online) {
        bonsaiStatus.className = "status-pill online";
        bonsaiStatus.innerHTML = '<span class="dot"></span> Bonsai 2: Готов';
      } else {
        bonsaiStatus.className = "status-pill simple";
        bonsaiStatus.innerHTML = '<span class="dot"></span> Режим: Simple Mode';
      }
    } catch (e) {
      dtStatus.className = "status-pill offline";
      dtStatus.innerHTML = '<span class="dot"></span> Backend Офлайн';
    }
  }

  checkHealth();
  setInterval(checkHealth, 15000);

  // 2. Format & Quality Controls
  formatSelector.querySelectorAll(".segment-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      formatSelector.querySelectorAll(".segment-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedFormat = btn.dataset.format;
    });
  });

  qualitySelector.querySelectorAll(".segment-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      qualitySelector.querySelectorAll(".segment-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedQuality = btn.dataset.quality;
    });
  });

  // 3. Advanced Toggle
  advancedToggle.addEventListener("click", () => {
    const isCollapsed = advancedContent.classList.contains("collapsed");
    if (isCollapsed) {
      advancedContent.classList.remove("collapsed");
      advancedToggle.classList.add("expanded");
    } else {
      advancedContent.classList.add("collapsed");
      advancedToggle.classList.remove("expanded");
    }
  });

  // 4. Generate Images
  generateBtn.addEventListener("click", startGeneration);
  promptInput.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      startGeneration();
    }
  });

  async function startGeneration() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      promptInput.focus();
      return;
    }

    // Build advanced overrides if filled
    const advanced = {};
    if (advPreparedPrompt.value.trim()) advanced.prepared_prompt = advPreparedPrompt.value.trim();
    if (advNegPrompt.value.trim()) advanced.negative_prompt = advNegPrompt.value.trim();
    if (advSeed.value !== "-1" && advSeed.value !== "") advanced.seed = parseInt(advSeed.value);
    if (advSteps.value) advanced.steps = parseInt(advSteps.value);
    if (advWidth.value) advanced.width = parseInt(advWidth.value);
    if (advHeight.value) advanced.height = parseInt(advHeight.value);
    if (advRealismLora.value) advanced.realism_lora = parseFloat(advRealismLora.value);
    if (advNsfwLora.value) advanced.unrestricted_lora = parseFloat(advNsfwLora.value);

    // Reset UI
    generateBtn.disabled = true;
    progressSection.classList.remove("hidden");
    progressBar.style.width = "5%";
    progressText.textContent = "Подготавливаю промпт...";
    unrestrictedBadge.classList.add("hidden");
    detailsBtn.classList.add("hidden");
    resultsCount.textContent = "0 из 4";

    resetGridSlots();

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          format: selectedFormat,
          quality: selectedQuality,
          count: 4,
          advanced
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Ошибка запуска генерации");
      }

      const data = await res.json();
      currentTaskId = data.task_id;
      startPolling(currentTaskId);
    } catch (e) {
      alert(`Ошибка: ${e.message}`);
      finishGenerationUI();
    }
  }

  function resetGridSlots() {
    resultsGrid.innerHTML = "";
    for (let i = 1; i <= 4; i++) {
      const card = document.createElement("div");
      card.className = i === 1 ? "image-card loading" : "image-card placeholder";
      card.dataset.slot = i;
      card.innerHTML = `<div class="card-inner"><div class="slot-loader">${i}</div></div>`;
      resultsGrid.appendChild(card);
    }
  }

  // 5. Polling Loop
  function startPolling(taskId) {
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/tasks/${taskId}`);
        if (!res.ok) return;
        const task = await res.json();

        // Update progress UI
        progressText.textContent = task.current_step_text;
        progressBar.style.width = `${Math.max(5, Math.min(100, task.progress * 100))}%`;

        if (task.plan) {
          lastCompletedPlan = task.plan;
          if (task.plan.is_unrestricted) {
            unrestrictedBadge.classList.remove("hidden");
          }
        }

        // Render received images progressively
        const images = task.images || [];
        resultsCount.textContent = `${images.length} из ${task.total_count}`;

        images.forEach((img, idx) => {
          const slotEl = resultsGrid.querySelector(`[data-slot="${idx + 1}"]`);
          if (slotEl && !slotEl.querySelector("img")) {
            renderImageInSlot(slotEl, img, taskId, idx + 1);
          }
        });

        // Update loading slot indicator
        if (images.length < task.total_count && task.status === "generating") {
          const nextSlot = resultsGrid.querySelector(`[data-slot="${images.length + 1}"]`);
          if (nextSlot && !nextSlot.classList.contains("loading")) {
            nextSlot.className = "image-card loading";
          }
        }

        // Check completion or failure
        if (task.status === "completed" || task.status === "cancelled" || task.status === "failed") {
          clearInterval(pollingInterval);
          pollingInterval = null;
          finishGenerationUI();

          if (task.status === "failed") {
            alert(`Ошибка генерации: ${task.error || "Неизвестная ошибка"}`);
          } else if (task.status === "completed") {
            detailsBtn.classList.remove("hidden");
          }
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
    }, 1200);
  }

  function renderImageInSlot(slotEl, imgData, taskId, slotNum) {
    slotEl.className = "image-card";
    slotEl.innerHTML = `
      <img src="${imgData.url}" alt="Result ${slotNum}" loading="lazy">
      <div class="card-overlay">
        <div class="card-actions">
          <button class="action-btn download-btn" title="Скачать оригинал">📥 Скачать</button>
          <button class="action-btn similar-btn" title="Повторить с новым сидом">🔀 Похожее</button>
          <button class="action-btn improve-btn" title="Улучшить (Final)">✨ Улучшить</button>
          <button class="action-btn more-btn" title="Ещё 4 варианта">🔄 Ещё</button>
        </div>
      </div>
    `;

    // Click on image opens lightbox
    const imgEl = slotEl.querySelector("img");
    imgEl.addEventListener("click", () => {
      lightboxImg.src = imgData.url;
      lightbox.classList.remove("hidden");
    });

    // Action handlers
    slotEl.querySelector(".download-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      const a = document.createElement("a");
      a.href = imgData.url;
      a.download = imgData.filename;
      a.click();
    });

    slotEl.querySelector(".similar-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      remixAction("similar", taskId, imgData.seed);
    });

    slotEl.querySelector(".improve-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      remixAction("improve", taskId, imgData.seed);
    });

    slotEl.querySelector(".more-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      remixAction("more", taskId, imgData.seed);
    });
  }

  async function remixAction(action, taskId, seed) {
    generateBtn.disabled = true;
    progressSection.classList.remove("hidden");
    progressBar.style.width = "5%";
    progressText.textContent = `Запуск операции: ${action}...`;
    resetGridSlots();

    try {
      const res = await fetch("/api/remix", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, task_id: taskId, seed })
      });
      if (!res.ok) throw new Error("Remix request failed");
      const data = await res.json();
      currentTaskId = data.task_id;
      startPolling(currentTaskId);
    } catch (e) {
      alert(`Ошибка: ${e.message}`);
      finishGenerationUI();
    }
  }

  function finishGenerationUI() {
    generateBtn.disabled = false;
    setTimeout(() => {
      if (!pollingInterval) {
        progressSection.classList.add("hidden");
      }
    }, 4000);
  }

  // 6. Cancel Generation
  cancelBtn.addEventListener("click", async () => {
    if (!currentTaskId) return;
    try {
      await fetch(`/api/tasks/${currentTaskId}/cancel`, { method: "POST" });
      progressText.textContent = "Отменяется...";
    } catch (e) {
      console.error(e);
    }
  });

  // 7. Details Modal
  detailsBtn.addEventListener("click", () => {
    if (!lastCompletedPlan) return;
    detailsContent.innerHTML = `
      <div class="detail-row">
        <div class="detail-label">Намерение (Intent) & Профиль</div>
        <div class="detail-val">${lastCompletedPlan.intent || "other"} / <strong>${lastCompletedPlan.profile || "base"}</strong> (${lastCompletedPlan.planner_source || "auto"})</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Подготовленный Production Prompt</div>
        <div class="detail-val">${lastCompletedPlan.prompt}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Отрицательный промпт (Negative)</div>
        <div class="detail-val">${lastCompletedPlan.negative_prompt || "—"}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Геометрия и разрешение</div>
        <div class="detail-val">${lastCompletedPlan.orientation} (${lastCompletedPlan.width} × ${lastCompletedPlan.height} px, ${lastCompletedPlan.steps} шагов)</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Активные LoRA адаптеры</div>
        <div class="detail-val">${JSON.stringify(lastCompletedPlan.loras || [], null, 2)}</div>
      </div>
    `;
    detailsModal.classList.remove("hidden");
  });

  closeDetailsModal.addEventListener("click", () => detailsModal.classList.add("hidden"));
  detailsModal.querySelector(".modal-backdrop").addEventListener("click", () => detailsModal.classList.add("hidden"));

  // 8. History Drawer
  historyBtn.addEventListener("click", loadHistory);
  closeHistoryBtn.addEventListener("click", () => historyDrawer.classList.add("hidden"));

  async function loadHistory() {
    historyDrawer.classList.remove("hidden");
    historyList.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">Загрузка...</div>';
    try {
      const res = await fetch("/api/history");
      const records = await res.json();
      if (!records || records.length === 0) {
        historyList.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">История пуста</div>';
        return;
      }
      historyList.innerHTML = "";
      records.forEach((r) => {
        const item = document.createElement("div");
        item.className = "history-item";
        item.innerHTML = `
          <div class="history-prompt">${r.user_prompt}</div>
          <div class="history-meta">
            <span>${r.profile || "base"} · ${r.images?.length || 0} фото</span>
            <span>${r.timestamp?.slice(5, 16) || ""}</span>
          </div>
        `;
        item.addEventListener("click", () => {
          restoreHistoryItem(r);
          historyDrawer.classList.add("hidden");
        });
        historyList.appendChild(item);
      });
    } catch (e) {
      historyList.innerHTML = '<div style="color:var(--danger); font-size:13px;">Не удалось загрузить историю</div>';
    }
  }

  function restoreHistoryItem(record) {
    promptInput.value = record.user_prompt;
    lastCompletedPlan = {
      prompt: record.prepared_prompt,
      negative_prompt: record.negative_prompt,
      profile: record.profile,
      intent: record.intent,
      orientation: record.orientation,
      width: record.width,
      height: record.height,
      steps: record.steps,
      loras: record.loras,
      planner_source: "history"
    };
    resultsCount.textContent = `${record.images?.length || 0} из ${record.images?.length || 4}`;
    detailsBtn.classList.remove("hidden");

    resultsGrid.innerHTML = "";
    (record.images || []).forEach((img, idx) => {
      const card = document.createElement("div");
      card.className = "image-card";
      card.dataset.slot = idx + 1;
      renderImageInSlot(card, img, record.task_id, idx + 1);
      resultsGrid.appendChild(card);
    });
  }

  // 9. Lightbox
  closeLightbox.addEventListener("click", () => lightbox.classList.add("hidden"));
  lightbox.querySelector(".lightbox-backdrop").addEventListener("click", () => lightbox.classList.add("hidden"));
});
