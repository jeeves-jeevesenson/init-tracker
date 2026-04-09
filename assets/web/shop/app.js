const statusEl = document.getElementById("shop-status");
const playerNameEl = document.getElementById("player-name");
const playerCurrencyEl = document.getElementById("player-currency");
const catalogListEl = document.getElementById("catalog-list");
const refreshButton = document.getElementById("refresh-button");
const playerPickerShellEl = document.getElementById("player-picker-shell");
const playerPickerSelectEl = document.getElementById("player-picker-select");
const playerPickerLoadButtonEl = document.getElementById("player-picker-load-button");

const REQUIRED_IDS = [
  "shop-status",
  "player-name",
  "player-currency",
  "catalog-list",
  "refresh-button",
  "player-picker-shell",
  "player-picker-select",
  "player-picker-load-button",
];

const state = {
  playerName: "",
  playerResolvedMode: "auto",
  manualPlayerOptions: [],
  currency: { gp: 0, sp: 0, cp: 0 },
  inventorySummary: { item_count: 0, distinct_count: 0 },
  catalog: [],
  inFlightItemKey: "",
  lastLoadHadError: false,
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
    const error = new Error(message);
    error.status = Number(response.status || 0);
    error.detail = detail;
    throw error;
  }
  return body || {};
};

const setPlayerPickerVisible = (visible) => {
  playerPickerShellEl.classList.toggle("hidden", !visible);
};

const renderPlayerPicker = () => {
  const existing = new Set(Array.from(playerPickerSelectEl.options).map((option) => option.value));
  state.manualPlayerOptions.forEach((name) => {
    if (existing.has(name)) return;
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    playerPickerSelectEl.appendChild(option);
  });
  playerPickerSelectEl.value = state.playerName || "";
  playerPickerLoadButtonEl.disabled = !playerPickerSelectEl.value;
};

const listCharacterNames = async () => {
  const payload = await fetchJson("/api/characters");
  const files = Array.isArray(payload?.files) ? payload.files : [];
  const normalized = files
    .map((file) => String(file || "").trim())
    .filter((name) => name.length > 0);
  return normalized.sort((left, right) => left.localeCompare(right));
};

const hydratePlayerState = (payload) => {
  const player = payload?.player || {};
  const name = String(player?.name || "").trim();
  if (!name) {
    throw new Error("Player payload is missing a name.");
  }
  state.playerName = name;
  state.currency = {
    gp: Number(player?.currency?.gp || 0),
    sp: Number(player?.currency?.sp || 0),
    cp: Number(player?.currency?.cp || 0),
  };
  state.inventorySummary = {
    item_count: Number(player?.inventory_summary?.item_count || 0),
    distinct_count: Number(player?.inventory_summary?.distinct_count || 0),
  };
};

const loadPlayerStateForMe = async () => {
  const payload = await fetchJson("/api/shop/me");
  hydratePlayerState(payload);
};

const loadPlayerStateForName = async (name) => {
  const payload = await fetchJson(`/api/shop/players/${encodeURIComponent(name)}`);
  hydratePlayerState(payload);
};

const loadCatalog = async () => {
  const payload = await fetchJson("/api/shop/catalog");
  state.catalog = Array.isArray(payload?.entries) ? payload.entries : [];
};

const renderHeader = () => {
  playerNameEl.textContent = state.playerName || "—";
  playerCurrencyEl.textContent = formatCurrency(state.currency);
};

const itemKey = (entry) => `${entry?.item_bucket || ""}:${entry?.item_id || ""}`;

const renderCatalog = () => {
  if (!state.catalog.length) {
    catalogListEl.innerHTML = "<p class=\"empty-catalog\">No enabled catalog entries found.</p>";
    return;
  }

  catalogListEl.innerHTML = "";
  state.catalog.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "card";

    const stock = document.createElement("p");
    stock.className = "stock";
    const stockUnlimited = Boolean(entry?.stock_unlimited === true);
    const stockRemaining = Number(entry?.stock_remaining ?? 0);
    const soldOut = !stockUnlimited && stockRemaining <= 0;
    stock.classList.toggle("sold-out", soldOut);
    stock.textContent = stockUnlimited ? "Stock: Unlimited" : `Stock: ${Math.max(0, stockRemaining)}`;

    const title = document.createElement("h3");
    title.className = "item-name";
    title.textContent = String(entry?.name || entry?.item_id || "Unknown item");

    const price = document.createElement("p");
    price.className = "price";
    price.textContent = formatCurrency(entry?.price || {});

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
    const playerUnavailable = !state.playerName;
    quantityInput.disabled = busyForRow || playerUnavailable;
    buyButton.disabled = busyForRow || playerUnavailable || soldOut;

    buyButton.addEventListener("click", () => buyItem(entry, quantityInput));

    actions.appendChild(quantityInput);
    actions.appendChild(buyButton);

    card.appendChild(stock);
    card.appendChild(title);
    card.appendChild(price);
    card.appendChild(actions);
    catalogListEl.appendChild(card);
  });
};

const setInFlightRow = (entryOrNull) => {
  state.inFlightItemKey = entryOrNull ? itemKey(entryOrNull) : "";
  renderCatalog();
};

const playShopAlertSound = (fileName) => {
  try {
    const audio = new Audio(`/assets/web/shop/${fileName}`);
    const playback = audio.play();
    if (playback && typeof playback.catch === "function") {
      playback.catch(() => {});
    }
  } catch (_error) {
    // Ignore audio playback errors so alerts still show.
  }
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
    await fetchJson(`/api/shop/players/${encodeURIComponent(state.playerName)}/purchase`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await Promise.all([loadPlayerStateForName(state.playerName), loadCatalog()]);
    renderHeader();
    renderCatalog();
    setStatus(`Purchase successful: ${quantity} × ${entry?.name || entry?.item_id}.`, "ok");
  } catch (error) {
    const isInsufficientFunds = String(error.message || "").toLowerCase().includes("insufficient funds");
    if (isInsufficientFunds) {
      setStatus("DAMN! Broke wizza alert. Wizza, how you gonna borrow a coin?", "error");
      playShopAlertSound("alarm.wav");
    } else {
      const message = error.status === 409
        ? `Purchase failed: ${error.message} (currency may be outdated; refresh and retry).`
        : `Purchase failed: ${error.message}`;
      setStatus(message, "error");
    }
  } finally {
    setInFlightRow(null);
  }
};

const reload = async () => {
  refreshButton.disabled = true;
  playerPickerLoadButtonEl.disabled = true;
  setStatus("Loading player and catalog…", "info");
  try {
    state.playerResolvedMode = "auto";
    const [playerResult, catalogResult] = await Promise.allSettled([loadPlayerStateForMe(), loadCatalog()]);
    if (playerResult.status === "rejected") {
      const playerError = playerResult.reason;
      if (playerError.status === 404 && String(playerError.message || "").toLowerCase().includes("assigned character")) {
        const names = await listCharacterNames();
        state.manualPlayerOptions = names;
        state.playerResolvedMode = "manual";
        state.playerName = "";
        setPlayerPickerVisible(true);
        renderPlayerPicker();
        if (catalogResult.status === "rejected") {
          throw catalogResult.reason;
        }
        renderHeader();
        renderCatalog();
        state.lastLoadHadError = false;
        setStatus("No assigned player was detected. Select who you are to continue.", "info");
        return;
      }
      throw playerError;
    }
    if (catalogResult.status === "rejected") {
      throw catalogResult.reason;
    }
    setPlayerPickerVisible(false);
    renderHeader();
    renderCatalog();
    state.lastLoadHadError = false;
    setStatus(`Loaded ${state.catalog.length} item${state.catalog.length === 1 ? "" : "s"} for ${state.playerName}.`, "ok");
  } catch (error) {
    state.lastLoadHadError = true;
    setPlayerPickerVisible(false);
    renderHeader();
    renderCatalog();
    setStatus(`Load failed: ${error.message}`, "error");
  } finally {
    refreshButton.disabled = false;
    if (state.playerResolvedMode === "manual") {
      playerPickerLoadButtonEl.disabled = !playerPickerSelectEl.value;
    }
  }
};

const init = async () => {
  assertRequiredElements();
  playerPickerSelectEl.addEventListener("change", () => {
    playerPickerLoadButtonEl.disabled = !playerPickerSelectEl.value;
  });
  playerPickerLoadButtonEl.addEventListener("click", async () => {
    const selected = String(playerPickerSelectEl.value || "").trim();
    if (!selected) {
      setStatus("Select a player before continuing.", "error");
      return;
    }
    refreshButton.disabled = true;
    playerPickerLoadButtonEl.disabled = true;
    setStatus(`Loading shop data for ${selected}…`, "info");
    try {
      await Promise.all([loadPlayerStateForName(selected), loadCatalog()]);
      renderPlayerPicker();
      renderHeader();
      renderCatalog();
      setStatus(`Loaded ${state.catalog.length} item${state.catalog.length === 1 ? "" : "s"} for ${state.playerName}.`, "ok");
    } catch (error) {
      setStatus(`Load failed: ${error.message}`, "error");
    } finally {
      refreshButton.disabled = false;
      playerPickerLoadButtonEl.disabled = !playerPickerSelectEl.value;
    }
  });
  refreshButton.addEventListener("click", reload);
  await reload();
};

init().catch((error) => {
  setStatus(`Shop failed to start: ${error.message}`, "error");
});
