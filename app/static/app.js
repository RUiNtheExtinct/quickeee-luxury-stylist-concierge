const form = document.querySelector("#stylist-form");
const promptInput = document.querySelector("#prompt");
const maxPriceInput = document.querySelector("#max-price");
const itemsEl = document.querySelector("#items");
const stageSection = document.querySelector("#stage-section");
const inventorySentinel = document.querySelector("#inventory-sentinel");
const traceEl = document.querySelector("#trace");
const noteEl = document.querySelector("#stylist-note");
const noteWrap = document.querySelector("#note-wrap");
const totalEl = document.querySelector("#total-price");
const titleEl = document.querySelector("#result-title");
const eyebrowEl = document.querySelector("#result-eyebrow");
const cacheEl = document.querySelector("#cache-state");
const railEl = document.querySelector("#rail");
const railCountEl = document.querySelector("#rail-count");
const loadMoreButton = document.querySelector("#load-more");
const responseJsonEl = document.querySelector("#response-json");
const helpModal = document.querySelector("#help-modal");
const helpButton = document.querySelector("#help-button");
const helpClose = document.querySelector("#help-close");
const debugBackend = document.querySelector("#debug-backend");
const debugCache = document.querySelector("#debug-cache");
const debugEmbedding = document.querySelector("#debug-embedding");
const debugLlm = document.querySelector("#debug-llm");

const genderSeg = document.querySelector("#gender-seg");
const accessorySeg = document.querySelector("#accessory-seg");

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

// Sticky styling preferences (no accounts — just this browser).
const prefs = { gender: "either", accessories: "auto" };
function loadPrefs() {
  try {
    prefs.gender = window.localStorage?.getItem("quickeee-gender") || "either";
    prefs.accessories = window.localStorage?.getItem("quickeee-accessories") || "auto";
  } catch {
    /* storage may be unavailable */
  }
  applySegState(genderSeg, "gender", prefs.gender);
  applySegState(accessorySeg, "accessories", prefs.accessories);
}
function applySegState(group, key, value) {
  if (!group) return;
  group.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset[key] === value);
  });
}
function wireSegment(group, key, storageKey) {
  if (!group) return;
  group.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      prefs[key] = button.dataset[key];
      applySegState(group, key, prefs[key]);
      try {
        window.localStorage?.setItem(storageKey, prefs[key]);
      } catch {
        /* ignore */
      }
    });
  });
}
const catalogPageSize = 24;
let catalogTotal = 0;
let catalogOffset = 0;
let catalogLoading = false;
let catalogComplete = false;

function refreshIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

async function loadHealth() {
  const response = await fetch("/health");
  const data = await response.json();
  catalogTotal = data.catalog_items;
  document.querySelector("#catalog-count").textContent = data.catalog_items;
  document.querySelector("#vector-backend").textContent = data.vector_backend;
  debugBackend.textContent = data.vector_backend;
  debugEmbedding.textContent = data.embedding_model || data.embedding_provider || "local";
  debugLlm.textContent = data.llm_provider || "local";
  updateRailCount();
}

async function loadRail() {
  if (catalogLoading || catalogComplete) return;
  catalogLoading = true;
  loadMoreButton.disabled = true;
  loadMoreButton.querySelector("span").textContent = "Loading inventory";
  let data = [];
  try {
    const response = await fetch(`/api/v1/catalog?limit=${catalogPageSize}&offset=${catalogOffset}`);
    data = await response.json();
  } catch {
    catalogLoading = false;
    railCountEl.textContent = "Inventory unavailable";
    return;
  }
  // Eager-load the first page so the visible rows always paint (lazy-loading a
  // big batch at once left some tiles blank until a hover/scroll repaint).
  const eager = catalogOffset === 0;
  railEl.insertAdjacentHTML(
    "beforeend",
    data
      .map(
        (item) => `
          <figure class="rail-card">
            <div class="rail-image">
              <img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}" loading="${eager ? "eager" : "lazy"}" decoding="async">
            </div>
            <figcaption>
              <strong>${escapeHtml(item.brand)}</strong>
              <span>${escapeHtml(item.name)}</span>
            </figcaption>
          </figure>
        `,
      )
      .join(""),
  );
  catalogOffset += data.length;
  catalogComplete = data.length < catalogPageSize || (catalogTotal > 0 && catalogOffset >= catalogTotal);
  catalogLoading = false;
  updateRailCount();
  refreshIcons();
}

function renderItems(items) {
  itemsEl.classList.remove("empty", "is-loading");
  itemsEl.innerHTML = items
    .map((item, index) => {
      const gender = item.gender && item.gender !== "unisex" ? `${escapeHtml(item.gender)}'s` : "unisex";
      const colorTag =
        item.color && item.color !== "unknown" ? `<span class="tag">${escapeHtml(item.color)}</span>` : "";
      const number = String(index + 1).padStart(2, "0");
      return `
        <article class="item" data-index="No ${number}" style="animation-delay:${index * 80}ms">
          <div class="item-media">
            <img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}" loading="eager" decoding="async">
          </div>
          <div class="item-info">
            <div class="item-meta">
              <span class="tag">${escapeHtml(item.category)}</span>
              <span class="tag">${gender}</span>
              ${colorTag}
              <span class="tag price">${money.format(item.price)}</span>
            </div>
            <h3>${escapeHtml(item.name)}</h3>
            <p>${escapeHtml(item.reason)}</p>
            <div class="item-meta"><span>${escapeHtml(item.brand)}</span></div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderSkeleton(count = 3) {
  itemsEl.classList.add("is-loading");
  itemsEl.innerHTML = Array.from({ length: count })
    .map(
      () => `
        <div class="skeleton">
          <div class="sk-media shimmer"></div>
          <div class="sk-lines">
            <div class="sk-line short shimmer"></div>
            <div class="sk-line med shimmer"></div>
            <div class="sk-line shimmer"></div>
          </div>
        </div>
      `,
    )
    .join("");
}

function renderTrace(trace) {
  if (!trace.length) {
    traceEl.innerHTML = "<li>No trace returned for this response.</li>";
    return;
  }
  traceEl.innerHTML = trace
    .map((step) => `<li><strong>${escapeHtml(step.step)}</strong> — ${escapeHtml(step.detail)}</li>`)
    .join("");
}

function setMode(mode) {
  document.body.classList.toggle("engineer-mode", mode === "engineer");
  document.body.classList.toggle("atelier-mode", mode !== "engineer");
  document.querySelectorAll("[data-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  try {
    window.localStorage?.setItem("quickeee-mode", mode);
  } catch {
    // Storage can be unavailable in locked-down preview browsers.
  }
}

async function submitPrompt(event) {
  event.preventDefault();
  const prompt = promptInput.value.trim();
  if (!prompt) return;

  form.classList.add("loading");
  stageSection.hidden = false;
  eyebrowEl.textContent = "Composing";
  titleEl.textContent = "Composing your look";
  totalEl.textContent = "···";
  noteWrap.hidden = true;
  renderSkeleton();
  traceEl.innerHTML = "<li>Retrieving inventory…</li>";
  responseJsonEl.textContent = "{}";
  // Scroll the result into view immediately so the user sees progress.
  stageSection.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const payload = { prompt, include_trace: true, gender: prefs.gender, accessories: prefs.accessories };
    if (maxPriceInput.value) payload.max_price = Number(maxPriceInput.value);
    const response = await fetch("/api/v1/style-me", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(readableError(errorText));
    }
    const data = await response.json();
    renderItems(data.recommended_items);
    renderTrace(data.trace);
    responseJsonEl.textContent = JSON.stringify(data, null, 2);
    noteEl.textContent = data.stylist_note;
    noteWrap.hidden = !data.stylist_note;
    totalEl.textContent = money.format(data.total_price);
    eyebrowEl.textContent = data.cache_hit ? "From cache" : "The selection";
    titleEl.textContent = data.cache_hit ? "Recalled look" : "Look composed";
    cacheEl.textContent = data.cache_hit ? "hit" : "stored";
    debugCache.textContent = data.cache_hit ? "hit" : "stored";
  } catch (error) {
    eyebrowEl.textContent = "Needs attention";
    titleEl.textContent = "The concierge paused";
    noteWrap.hidden = false;
    noteEl.textContent = error.message;
    traceEl.innerHTML = `<li>${escapeHtml(error.message)}</li>`;
    responseJsonEl.textContent = JSON.stringify({ error: error.message }, null, 2);
  } finally {
    form.classList.remove("loading");
    refreshIcons();
  }
}

function readableError(errorText) {
  try {
    const parsed = JSON.parse(errorText);
    return parsed.detail || errorText;
  } catch {
    return errorText || "The stylist could not complete this request.";
  }
}

function updateRailCount() {
  const visible = Math.min(catalogOffset, catalogTotal || catalogOffset);
  if (!catalogOffset && !catalogTotal) {
    railCountEl.textContent = "Loading inventory…";
  } else {
    railCountEl.textContent = catalogTotal ? `Showing ${visible} of ${catalogTotal}` : `Showing ${visible} pieces`;
  }
  loadMoreButton.disabled = catalogLoading || catalogComplete;
  // Only show the manual button once at least one page is in; scroll handles the rest.
  loadMoreButton.hidden = catalogComplete || catalogOffset === 0;
  loadMoreButton.querySelector("span").textContent = catalogComplete ? "Inventory loaded" : "Load more inventory";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.dataset.prompt;
    promptInput.focus();
  });
});

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

helpButton.addEventListener("click", () => {
  helpModal.hidden = false;
  helpClose.focus();
});

helpClose.addEventListener("click", () => {
  helpModal.hidden = true;
  helpButton.focus();
});

helpModal.addEventListener("click", (event) => {
  if (event.target === helpModal) {
    helpModal.hidden = true;
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !helpModal.hidden) {
    helpModal.hidden = true;
    helpButton.focus();
  }
});

// Cmd/Ctrl+Enter submits the brief from within the textarea.
promptInput.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    form.requestSubmit();
  }
});

loadMoreButton.addEventListener("click", loadRail);

form.addEventListener("submit", submitPrompt);

let savedMode = "atelier";
try {
  savedMode = window.localStorage?.getItem("quickeee-mode") || "atelier";
} catch {
  savedMode = "atelier";
}
setMode(savedMode);
loadPrefs();
wireSegment(genderSeg, "gender", "quickeee-gender");
wireSegment(accessorySeg, "accessories", "quickeee-accessories");

// Reveal the app only once fonts have painted — prevents the FOUC where the
// serif/icons hadn't loaded and ghost buttons blended into the paper.
function revealApp() {
  document.body.classList.add("fonts-ready");
  refreshIcons();
}
if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(revealApp);
  // Safety net in case fonts.ready never resolves (e.g. blocked CDN).
  setTimeout(revealApp, 1200);
} else {
  revealApp();
}

// Lazy-load inventory only when the user scrolls near it — keeps first paint
// fast and stops the heavy image grid from ever bleeding into the hero.
if ("IntersectionObserver" in window && inventorySentinel) {
  const observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        loadRail();
        if (catalogComplete) observer.disconnect();
      }
    },
    { rootMargin: "300px 0px" },
  );
  observer.observe(inventorySentinel);
} else {
  loadRail();
}

loadHealth();
