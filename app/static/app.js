const form = document.querySelector("#stylist-form");
const promptInput = document.querySelector("#prompt");
const maxPriceInput = document.querySelector("#max-price");
const itemsEl = document.querySelector("#items");
const traceEl = document.querySelector("#trace");
const noteEl = document.querySelector("#stylist-note");
const totalEl = document.querySelector("#total-price");
const titleEl = document.querySelector("#result-title");
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

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const catalogPageSize = 16;
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
  updateRailCount();
}

async function loadRail() {
  if (catalogLoading || catalogComplete) return;
  catalogLoading = true;
  loadMoreButton.disabled = true;
  loadMoreButton.querySelector("span").textContent = "Loading inventory";
  const response = await fetch(`/api/v1/catalog?limit=${catalogPageSize}&offset=${catalogOffset}`);
  const data = await response.json();
  railEl.insertAdjacentHTML(
    "beforeend",
    data
      .map(
        (item) => `
          <figure class="rail-card">
            <div class="rail-image">
              <img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}" loading="lazy" decoding="async">
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
  itemsEl.classList.remove("empty");
  itemsEl.innerHTML = items
    .map(
      (item) => `
        <article class="item">
          <div class="item-media">
            <img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}" loading="eager" decoding="async">
          </div>
          <div class="item-info">
            <small>${escapeHtml(item.brand)} / ${escapeHtml(item.category)} / ${money.format(item.price)}</small>
            <h2>${escapeHtml(item.name)}</h2>
            <p>${escapeHtml(item.reason)}</p>
          </div>
        </article>
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
    .map((step) => `<li><strong>${escapeHtml(step.step)}</strong>: ${escapeHtml(step.detail)}</li>`)
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
  titleEl.textContent = "Composing";
  traceEl.innerHTML = "<li>Retrieving inventory...</li>";
  responseJsonEl.textContent = "{}";

  try {
    const payload = { prompt, include_trace: true };
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
    totalEl.textContent = money.format(data.total_price);
    titleEl.textContent = data.cache_hit ? "Pulled from cache" : "Look approved";
    cacheEl.textContent = data.cache_hit ? "hit" : "stored";
    debugCache.textContent = data.cache_hit ? "hit" : "stored";
    document.scrollingElement.scrollTop = 0;
  } catch (error) {
    titleEl.textContent = "Needs attention";
    traceEl.innerHTML = `<li>${error.message}</li>`;
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
  railCountEl.textContent = catalogTotal ? `Showing ${visible} of ${catalogTotal}` : `Showing ${visible} items`;
  loadMoreButton.disabled = catalogLoading || catalogComplete;
  loadMoreButton.hidden = catalogComplete;
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

loadMoreButton.addEventListener("click", loadRail);

form.addEventListener("submit", submitPrompt);
let savedMode = "atelier";
try {
  savedMode = window.localStorage?.getItem("quickeee-mode") || "atelier";
} catch {
  savedMode = "atelier";
}
setMode(savedMode);
Promise.all([loadHealth(), loadRail()]).finally(refreshIcons);
