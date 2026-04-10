const statusEl = document.getElementById("shop-status");
const playerNameEl = document.getElementById("player-name");
const playerCurrencyEl = document.getElementById("player-currency");
const catalogListEl = document.getElementById("catalog-list");
const refreshButton = document.getElementById("refresh-button");
const playerPickerShellEl = document.getElementById("player-picker-shell");
const playerPickerSelectEl = document.getElementById("player-picker-select");
const playerPickerLoadButtonEl = document.getElementById("player-picker-load-button");
const filterSearchEl = document.getElementById("filter-search");
const filterBucketEl = document.getElementById("filter-bucket");
const filterTierEl = document.getElementById("filter-tier");
const filterCountEl = document.getElementById("filter-count");

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

const RARITY_ORDER = ["common", "uncommon", "rare", "very rare", "legendary", "artifact"];
const RARITY_COLORS = {
  common: "#94a3b8",
  uncommon: "#4ade80",
  rare: "#60a5fa",
  "very rare": "#c084fc",
  legendary: "#fb923c",
  artifact: "#fbbf24",
};

const state = {
  playerName: "",
  playerResolvedMode: "auto",
  manualPlayerOptions: [],
  currency: { gp: 0, sp: 0, cp: 0 },
  inventorySummary: { item_count: 0, distinct_count: 0 },
  catalog: [],
  inFlightItemKey: "",
  lastLoadHadError: false,
  filterText: "",
  filterBucket: "",
  filterTier: "",
};

const REFRESH_BUTTON_LABEL = "Refresh";
const PICKER_LOAD_BUTTON_LABEL = "Use player";

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

const setRefreshUi = ({ loading = false, message = "" } = {}) => {
  refreshButton.disabled = loading;
  refreshButton.textContent = loading ? "Refreshing…" : REFRESH_BUTTON_LABEL;
  if (message) {
    refreshButton.title = message;
  } else {
    refreshButton.removeAttribute("title");
  }
};

const setPickerLoadUi = ({ loading = false, allowInteraction = false } = {}) => {
  playerPickerLoadButtonEl.textContent = loading ? "Loading…" : PICKER_LOAD_BUTTON_LABEL;
  if (loading) {
    playerPickerLoadButtonEl.disabled = true;
    return;
  }
  playerPickerLoadButtonEl.disabled = !allowInteraction || !playerPickerSelectEl.value;
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

const filteredCatalog = () => {
  const text = state.filterText.trim().toLowerCase();
  const bucket = state.filterBucket;
  const tier = state.filterTier;
  return state.catalog.filter((entry) => {
    if (bucket && (entry?.item_bucket || "") !== bucket) return false;
    if (tier && String(entry?.item_tier || "").toUpperCase() !== tier.toUpperCase()) return false;
    if (text) {
      const haystack = [
        entry?.name || "",
        entry?.item_id || "",
        entry?.description || "",
        entry?.rarity || "",
        entry?.shop_category || "",
      ].join(" ").toLowerCase();
      if (!haystack.includes(text)) return false;
    }
    return true;
  });
};

const rarityBadge = (rarity) => {
  if (!rarity) return null;
  const badge = document.createElement("span");
  badge.className = "badge badge-rarity";
  badge.textContent = rarity;
  const color = RARITY_COLORS[rarity.toLowerCase()] || "#94a3b8";
  badge.style.setProperty("--badge-color", color);
  return badge;
};

const tierBadge = (tier) => {
  if (!tier) return null;
  const badge = document.createElement("span");
  badge.className = `badge badge-tier badge-tier-${tier.toLowerCase()}`;
  badge.textContent = `Tier ${tier}`;
  return badge;
};

const renderCatalog = () => {
  const visible = filteredCatalog();
  if (filterCountEl) {
    filterCountEl.textContent = state.catalog.length
      ? `${visible.length} / ${state.catalog.length} items`
      : "";
  }

  if (!state.catalog.length) {
    catalogListEl.innerHTML = "<p class=\"empty-catalog\">No enabled catalog entries found.</p>";
    return;
  }

  if (!visible.length) {
    catalogListEl.innerHTML = "<p class=\"empty-catalog\">No items match the current filter. Try clearing your search.</p>";
    return;
  }

  catalogListEl.innerHTML = "";
  visible.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "card";

    const stock = document.createElement("p");
    stock.className = "stock";
    const stockUnlimited = Boolean(entry?.stock_unlimited === true);
    const stockRemaining = Number(entry?.stock_remaining ?? 0);
    const soldOut = !stockUnlimited && stockRemaining <= 0;
    const lowStock = !stockUnlimited && stockRemaining > 0 && stockRemaining <= 3;
    stock.classList.toggle("sold-out", soldOut);
    stock.classList.toggle("low-stock", lowStock);
    stock.textContent = stockUnlimited
      ? "Stock: Unlimited"
      : soldOut
        ? "Sold out"
        : lowStock
          ? `Low stock: ${Math.max(0, stockRemaining)} left`
          : `Stock: ${Math.max(0, stockRemaining)}`;

    const titleRow = document.createElement("div");
    titleRow.className = "item-title-row";

    const title = document.createElement("h3");
    title.className = "item-name";
    title.textContent = String(entry?.name || entry?.item_id || "Unknown item");

    const badgesEl = document.createElement("div");
    badgesEl.className = "item-badges";
    const rBadge = rarityBadge(entry?.rarity);
    if (rBadge) badgesEl.appendChild(rBadge);
    const tBadge = tierBadge(entry?.item_tier);
    if (tBadge) badgesEl.appendChild(tBadge);
    if (entry?.requires_attunement) {
      const ab = document.createElement("span");
      ab.className = "badge badge-attunement";
      ab.textContent = "Attunement";
      badgesEl.appendChild(ab);
    }
    titleRow.append(title, badgesEl);

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
    const purchaseBlocked = busyForRow || playerUnavailable || soldOut;
    quantityInput.disabled = busyForRow || playerUnavailable;
    buyButton.disabled = purchaseBlocked;
    quantityInput.title = playerUnavailable
      ? "Select a player before setting quantity."
      : busyForRow
        ? "Purchase in progress for this item."
        : "";
    buyButton.textContent = busyForRow
      ? "Buying…"
      : soldOut
        ? "Sold out"
        : playerUnavailable
          ? "Pick player"
          : "Buy";
    buyButton.title = soldOut
      ? "This item is out of stock."
      : playerUnavailable
        ? "Select your player to purchase items."
        : busyForRow
          ? "Purchase in progress."
          : "";
    card.classList.toggle("sold-out-card", soldOut);
    card.classList.toggle("busy-card", busyForRow);

    buyButton.addEventListener("click", () => buyItem(entry, quantityInput));

    actions.appendChild(quantityInput);
    actions.appendChild(buyButton);

    card.appendChild(stock);
    card.appendChild(titleRow);
    card.appendChild(price);
    card.appendChild(actions);

    if (entry?.description) {
      const descToggle = document.createElement("details");
      descToggle.className = "item-desc-toggle";
      const sum = document.createElement("summary");
      sum.textContent = "Description";
      const desc = document.createElement("p");
      desc.className = "item-desc";
      desc.textContent = String(entry.description);
      descToggle.append(sum, desc);
      card.appendChild(descToggle);
    }

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
  setRefreshUi({ loading: true, message: "Purchase in progress." });
  setStatus(`Purchasing ${quantity} × ${entry?.name || entry?.item_id}...`, "info");
  try {
    await fetchJson(`/api/shop/players/${encodeURIComponent(state.playerName)}/purchase`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const [playerReloadResult, catalogReloadResult] = await Promise.allSettled([
      loadPlayerStateForName(state.playerName),
      loadCatalog(),
    ]);
    if (playerReloadResult.status === "fulfilled") {
      renderHeader();
    }
    if (catalogReloadResult.status === "fulfilled") {
      renderCatalog();
    }
    if (playerReloadResult.status === "fulfilled" && catalogReloadResult.status === "fulfilled") {
      state.lastLoadHadError = false;
      setStatus(`Purchase successful: ${quantity} × ${entry?.name || entry?.item_id}.`, "ok");
    } else {
      state.lastLoadHadError = true;
      const refreshIssues = [];
      if (playerReloadResult.status === "rejected") refreshIssues.push("player currency");
      if (catalogReloadResult.status === "rejected") refreshIssues.push("catalog stock");
      setStatus(
        `Purchase succeeded, but we could not fully refresh ${refreshIssues.join(" and ")}. Use Refresh before buying again.`,
        "error",
      );
    }
  } catch (error) {
    const isInsufficientFunds = String(error.message || "").toLowerCase().includes("insufficient funds");
    const lowerError = String(error.message || "").toLowerCase();
    const isOutOfStock = lowerError.includes("out of stock")
      || lowerError.includes("sold out")
      || lowerError.includes("insufficient stock");
    if (isInsufficientFunds) {
      setStatus("Purchase failed: you cannot afford this item. Check your current currency and try a smaller quantity.", "error");
      playShopAlertSound("alarm.wav");
    } else if (isOutOfStock) {
      setStatus("Purchase failed: this item is out of stock or does not have enough remaining quantity.", "error");
    } else {
      const message = error.status === 409
        ? `Purchase blocked: shop data changed. Refresh your currency/catalog, then retry this purchase. (${error.message})`
        : `Purchase failed: ${error.message}`;
      setStatus(message, "error");
    }
  } finally {
    setInFlightRow(null);
    setRefreshUi({ loading: false, message: state.lastLoadHadError ? "Refresh recommended before next purchase." : "" });
  }
};

const reload = async () => {
  setRefreshUi({ loading: true });
  setPickerLoadUi({ loading: true });
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
    setRefreshUi({ loading: false, message: state.lastLoadHadError ? "Last refresh failed. Retry before purchasing." : "" });
    if (state.playerResolvedMode === "manual") {
      setPickerLoadUi({ loading: false, allowInteraction: true });
    } else {
      setPickerLoadUi({ loading: false, allowInteraction: false });
    }
  }
};

const init = async () => {
  assertRequiredElements();
  if (filterSearchEl) {
    filterSearchEl.addEventListener("input", (e) => {
      state.filterText = e.target.value;
      renderCatalog();
    });
  }
  if (filterBucketEl) {
    filterBucketEl.addEventListener("change", (e) => {
      state.filterBucket = e.target.value;
      renderCatalog();
    });
  }
  if (filterTierEl) {
    filterTierEl.addEventListener("change", (e) => {
      state.filterTier = e.target.value;
      renderCatalog();
    });
  }
  playerPickerSelectEl.addEventListener("change", () => {
    if (state.playerResolvedMode === "manual") {
      setPickerLoadUi({ loading: false, allowInteraction: true });
    }
  });
  playerPickerLoadButtonEl.addEventListener("click", async () => {
    const selected = String(playerPickerSelectEl.value || "").trim();
    if (!selected) {
      setStatus("Select a player before continuing.", "error");
      return;
    }
    setRefreshUi({ loading: true });
    setPickerLoadUi({ loading: true });
    setStatus(`Loading shop data for ${selected}…`, "info");
    try {
      await Promise.all([loadPlayerStateForName(selected), loadCatalog()]);
      renderPlayerPicker();
      renderHeader();
      renderCatalog();
      state.lastLoadHadError = false;
      setStatus(`Loaded ${state.catalog.length} item${state.catalog.length === 1 ? "" : "s"} for ${state.playerName}.`, "ok");
    } catch (error) {
      state.lastLoadHadError = true;
      setStatus(`Load failed: ${error.message}`, "error");
    } finally {
      setRefreshUi({ loading: false, message: state.lastLoadHadError ? "Last refresh failed. Retry before purchasing." : "" });
      setPickerLoadUi({ loading: false, allowInteraction: true });
    }
  });
  refreshButton.addEventListener("click", reload);
  await reload();
};

init().catch((error) => {
  setStatus(`Shop failed to start: ${error.message}`, "error");
});
