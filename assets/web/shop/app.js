const statusEl = document.getElementById("shop-status");
const playerNameEl = document.getElementById("player-name");
const playerCurrencyEl = document.getElementById("player-currency");
const catalogListEl = document.getElementById("catalog-list");
const refreshButton = document.getElementById("refresh-button");

const REQUIRED_IDS = ["shop-status", "player-name", "player-currency", "catalog-list", "refresh-button"];

const state = {
  playerName: "",
  currency: { gp: 0, sp: 0, cp: 0 },
  inventorySummary: { total_items: 0, unique_items: 0 },
  catalog: [],
  inFlightItemKey: "",
};

const assertRequiredElements = () => {
  const missing = REQUIRED_IDS.filter((id) => !document.getElementById(id));
  if (!missing.length) return;
  throw new Error(`Shop template missing required IDs: ${missing.join(", ")}`);
};

const setStatus = (message, tone = "info") => {
  statusEl.textContent = message;
  statusEl.classList.remove("ok", "error", "info");
  statusEl.classList.add(tone);
};

const formatCurrency = (currency = {}) => {
  const gp = Number(currency.gp || 0);
  const sp = Number(currency.sp || 0);
  const cp = Number(currency.cp || 0);
  return `${gp} gp • ${sp} sp • ${cp} cp`;
};

const summarizeInventory = (items) => {
  const list = Array.isArray(items) ? items : [];
  const unique = new Set();
  let total = 0;
  list.forEach((entry) => {
    const qty = Math.max(1, Number(entry?.quantity || 1));
    total += qty;
    const id = String(entry?.id || "").trim();
    if (id) unique.add(id);
  });
  return { total_items: total, unique_items: unique.size };
};

const fetchJson = async (url, options = {}) => {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let body = null;
  try {
    body = await response.json();
  } catch (_error) {
    body = null;
  }
  if (!response.ok) {
    const detail = body && body.detail ? body.detail : `${response.status} ${response.statusText}`;
    const message = typeof detail === "string" ? detail : (detail?.message || detail?.error || "Request failed");
    throw new Error(message);
  }
  return body || {};
};

const loadPlayerByIp = async () => {
  const payload = await fetchJson("/api/characters/by_ip");
  const character = payload?.character || {};
  const name = String(character?.name || "").trim();
  if (!name) {
    throw new Error("Assigned player is missing a name.");
  }
  const inventory = character?.inventory || {};
  state.playerName = name;
  state.currency = {
    gp: Number(inventory?.currency?.gp || 0),
    sp: Number(inventory?.currency?.sp || 0),
    cp: Number(inventory?.currency?.cp || 0),
  };
  state.inventorySummary = summarizeInventory(inventory?.items);
};

const loadCatalog = async () => {
  const payload = await fetchJson("/api/shop/catalog");
  state.catalog = Array.isArray(payload?.entries) ? payload.entries : [];
};

const renderHeader = () => {
  playerNameEl.textContent = state.playerName || "—";
  const inv = state.inventorySummary;
  playerCurrencyEl.textContent = `${formatCurrency(state.currency)} (items: ${inv.total_items}, unique: ${inv.unique_items})`;
};

const itemKey = (entry) => `${entry?.item_bucket || ""}:${entry?.item_id || ""}`;

const renderCatalog = () => {
  if (!state.catalog.length) {
    catalogListEl.innerHTML = "<p>No enabled catalog entries found.</p>";
    return;
  }

  catalogListEl.innerHTML = "";
  state.catalog.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "card";

    const title = document.createElement("h3");
    title.textContent = String(entry?.name || entry?.item_id || "Unknown item");

    const meta = document.createElement("p");
    meta.className = "meta";
    const type = String(entry?.type || "—");
    const category = String(entry?.shop_category || "—");
    const bucket = String(entry?.item_bucket || "—");
    const path = String(entry?.definition_path || "—");
    meta.textContent = `Category: ${category} • Bucket: ${bucket} • Type: ${type} • Source: ${path}`;

    const price = document.createElement("p");
    price.className = "price";
    price.textContent = `Price: ${formatCurrency(entry?.price || {})}`;

    const actions = document.createElement("div");
    actions.className = "actions";

    const quantityInput = document.createElement("input");
    quantityInput.type = "number";
    quantityInput.min = "1";
    quantityInput.step = "1";
    quantityInput.value = "1";
    quantityInput.className = "quantity-input";

    const buyButton = document.createElement("button");
    buyButton.type = "button";
    buyButton.textContent = "Buy";

    const key = itemKey(entry);
    const busyForRow = state.inFlightItemKey === key;
    quantityInput.disabled = busyForRow;
    buyButton.disabled = busyForRow;

    buyButton.addEventListener("click", () => buyItem(entry, quantityInput));

    actions.appendChild(quantityInput);
    actions.appendChild(buyButton);

    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(price);
    card.appendChild(actions);
    catalogListEl.appendChild(card);
  });
};

const setInFlightRow = (entryOrNull) => {
  state.inFlightItemKey = entryOrNull ? itemKey(entryOrNull) : "";
  renderCatalog();
};

const buyItem = async (entry, quantityInputEl) => {
  if (!state.playerName) {
    setStatus("No assigned player found for this device/IP.", "error");
    return;
  }
  const quantity = Math.max(1, Number(quantityInputEl.value || 1));
  const payload = {
    item_id: String(entry?.item_id || ""),
    item_bucket: String(entry?.item_bucket || ""),
    quantity,
  };

  setInFlightRow(entry);
  setStatus(`Purchasing ${quantity} × ${entry?.name || entry?.item_id}...`, "info");
  try {
    const result = await fetchJson(`/api/shop/players/${encodeURIComponent(state.playerName)}/purchase`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (result?.player?.inventory?.currency) {
      const inventory = result.player.inventory;
      state.currency = {
        gp: Number(inventory.currency?.gp || 0),
        sp: Number(inventory.currency?.sp || 0),
        cp: Number(inventory.currency?.cp || 0),
      };
      state.inventorySummary = summarizeInventory(inventory?.items);
    } else {
      await loadPlayerByIp();
    }
    renderHeader();
    setStatus(`Purchase successful: ${quantity} × ${entry?.name || entry?.item_id}.`, "ok");
  } catch (error) {
    setStatus(`Purchase failed: ${error.message}`, "error");
  } finally {
    setInFlightRow(null);
  }
};

const reload = async () => {
  refreshButton.disabled = true;
  setStatus("Loading player and catalog...", "info");
  try {
    await Promise.all([loadPlayerByIp(), loadCatalog()]);
    renderHeader();
    renderCatalog();
    setStatus(`Loaded ${state.catalog.length} item${state.catalog.length === 1 ? "" : "s"} for ${state.playerName}.`, "ok");
  } catch (error) {
    renderHeader();
    renderCatalog();
    setStatus(`Load failed: ${error.message}`, "error");
  } finally {
    refreshButton.disabled = false;
  }
};

const init = async () => {
  assertRequiredElements();
  refreshButton.addEventListener("click", reload);
  await reload();
};

init().catch((error) => {
  setStatus(`Shop failed to start: ${error.message}`, "error");
});
