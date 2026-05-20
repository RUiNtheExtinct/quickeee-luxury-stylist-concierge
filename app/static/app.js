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

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

async function loadHealth() {
  const response = await fetch("/health");
  const data = await response.json();
  document.querySelector("#catalog-count").textContent = data.catalog_items;
  document.querySelector("#vector-backend").textContent = data.vector_backend;
}

async function loadRail() {
  const response = await fetch("/api/v1/catalog?limit=18");
  const data = await response.json();
  railEl.innerHTML = data
    .map(
      (item) => `
        <figure>
          <img src="${item.image_url}" alt="${item.name}" loading="lazy">
          <figcaption>${item.brand}<br>${item.name}</figcaption>
        </figure>
      `,
    )
    .join("");
}

function renderItems(items) {
  itemsEl.classList.remove("empty");
  itemsEl.innerHTML = items
    .map(
      (item) => `
        <article class="item">
          <img src="${item.image_url}" alt="${item.name}">
          <div class="item-info">
            <small>${item.brand} / ${item.category} / ${money.format(item.price)}</small>
            <h2>${item.name}</h2>
            <p>${item.reason}</p>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderTrace(trace) {
  traceEl.innerHTML = trace.map((step) => `<li><strong>${step.step}</strong>: ${step.detail}</li>`).join("");
}

async function submitPrompt(event) {
  event.preventDefault();
  const prompt = promptInput.value.trim();
  if (!prompt) return;

  form.classList.add("loading");
  titleEl.textContent = "Composing";
  traceEl.innerHTML = "<li>Retrieving inventory...</li>";

  try {
    const payload = { prompt, include_trace: true };
    if (maxPriceInput.value) payload.max_price = Number(maxPriceInput.value);
    const response = await fetch("/api/v1/style-me", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const data = await response.json();
    renderItems(data.recommended_items);
    renderTrace(data.trace);
    noteEl.textContent = data.stylist_note;
    totalEl.textContent = money.format(data.total_price);
    titleEl.textContent = data.cache_hit ? "Pulled from cache" : "Look approved";
    cacheEl.textContent = data.cache_hit ? "hit" : "stored";
    document.scrollingElement.scrollTop = 0;
  } catch (error) {
    titleEl.textContent = "Needs attention";
    traceEl.innerHTML = `<li>${error.message}</li>`;
  } finally {
    form.classList.remove("loading");
  }
}

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.dataset.prompt;
    promptInput.focus();
  });
});

form.addEventListener("submit", submitPrompt);
loadHealth();
loadRail();
