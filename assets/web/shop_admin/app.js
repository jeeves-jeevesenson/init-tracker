const rowsEl = document.getElementById("catalog-rows");
const statusEl = document.getElementById("status-banner");
const reloadButton = document.getElementById("reload-button");
const addRowButton = document.getElementById("add-row-button");
const validateButton = document.getElementById("validate-button");
const saveButton = document.getElementById("save-button");
const dirtyStateEl = document.getElementById("dirty-state");
const wealthRowsEl = document.getElementById("wealth-rows");
const wealthSummaryStatusEl = document.getElementById("wealth-summary-status");
const partyTotalGpEl = document.getElementById("party-total-gp");
const partyTotalSpEl = document.getElementById("party-total-sp");
const partyTotalCpEl = document.getElementById("party-total-cp");
const partyTotalCpValueEl = document.getElementById("party-total-cp-value");
const categorySuggestionsEl = document.getElementById("shop-category-suggestions");

const REQUIRED_IDS = [
  "catalog-rows",
  "status-banner",
  "reload-button",
  "add-row-button",
  "validate-button",
  "save-button",
  "dirty-state",
  "wealth-rows",
  "wealth-summary-status",
  "party-total-gp",
  "party-total-sp",
  "party-total-cp",
  "party-total-cp-value",
];

const ITEM_BUCKET_OPTIONS = ["weapon", "armor", "magic_item", "consumable"];
const DEFAULT_CATEGORY_SUGGESTIONS = ["weapons", "armor", "consumables", "scrolls", "magic_items"];

const assertRequiredElements = () => {
  const missing = REQUIRED_IDS.filter((id) => !document.getElementById(id));
  if (!missing.length) return;
  throw new Error(`Shop admin template missing required IDs: ${missing.join(", ")}`);
};

const state = {
  formatVersion: 1,
  entries: [],
  busy: false,
  dirty: false,
  revision: null,
  rowErrors: {},
  wealthPlayers: [],
  wealthPartyCurrency: { gp: 0, sp: 0, cp: 0 },
  wealthPartyTotalCp: 0,
};

const setStatus = (message, tone = "info") => {
  statusEl.textContent = message;
  statusEl.classList.remove("ok", "error", "info");
  statusEl.classList.add(tone);
};

const updateDirtyState = () => {
  dirtyStateEl.textContent = state.dirty ? "Unsaved changes" : "All changes saved";
  dirtyStateEl.classList.toggle("dirty", state.dirty);
};

const toNumberOrUndefined = (value) => {
  if (value === "" || value === null || value === undefined) return undefined;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
};

const editableFromNormalized = (entry = {}) => ({
  item_id: String(entry.item_id || "").trim(),
  item_bucket: String(entry.item_bucket || "").trim(),
  shop_category: String(entry.shop_category || "").trim(),
  enabled: entry.enabled !== false,
  price: {
    ...(entry.price && typeof entry.price === "object" ? entry.price : {}),
  },
  stock_limit: entry.stock_unlimited ? "" : (entry.stock_limit ?? ""),
  stock_sold: entry.stock_sold ?? 0,
  _readonly: {
    name: entry.name || "",
    type: entry.type || "",
    definition_path: entry.definition_path || "",
  },
});

const markDirty = () => {
  state.dirty = true;
  updateDirtyState();
};

const parseErrorDetail = (body, response) => {
  const detail = body && body.detail ? body.detail : `${response.status} ${response.statusText}`;
  const text = typeof detail === "string" ? detail : (detail?.message || detail?.error || "Request failed");
  const error = new Error(text);
  error.status = Number(response.status || 0);
  error.detail = detail;
  return error;
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
  if (!response.ok) throw parseErrorDetail(body, response);
  return body || {};
};

const buildPayload = () => ({
  format_version: Number(state.formatVersion || 1),
  expected_revision: state.revision || undefined,
  entries: state.entries.map((entry) => {
    const payloadEntry = {
      item_id: String(entry.item_id || "").trim(),
      item_bucket: String(entry.item_bucket || "").trim(),
      shop_category: String(entry.shop_category || "").trim(),
      enabled: Boolean(entry.enabled),
      price: {},
    };
    const gp = toNumberOrUndefined(entry.price?.gp);
    const sp = toNumberOrUndefined(entry.price?.sp);
    const cp = toNumberOrUndefined(entry.price?.cp);
    if (gp !== undefined) payloadEntry.price.gp = gp;
    if (sp !== undefined) payloadEntry.price.sp = sp;
    if (cp !== undefined) payloadEntry.price.cp = cp;

    const stockLimit = toNumberOrUndefined(entry.stock_limit);
    const stockSold = toNumberOrUndefined(entry.stock_sold);
    if (stockLimit !== undefined || stockSold !== undefined) {
      payloadEntry.stock = {};
      if (stockLimit !== undefined) payloadEntry.stock.limit = stockLimit;
      if (stockSold !== undefined) payloadEntry.stock.sold = stockSold;
    }
    return payloadEntry;
  }),
});

const setBusy = (busy) => {
  state.busy = Boolean(busy);
  [reloadButton, addRowButton, validateButton, saveButton].forEach((button) => { button.disabled = state.busy; });
  rowsEl.querySelectorAll("input,select,button").forEach((el) => { el.disabled = state.busy; });
};

const localValidationErrors = () => {
  const errors = {};
  const seen = new Set();
  state.entries.forEach((entry, index) => {
    const rowErrors = [];
    const itemId = String(entry.item_id || "").trim().toLowerCase();
    const bucket = String(entry.item_bucket || "").trim().toLowerCase();
    const category = String(entry.shop_category || "").trim();
    if (!itemId) rowErrors.push("item_id is required");
    if (!bucket) rowErrors.push("item_bucket is required");
    if (!category) rowErrors.push("shop_category is required");

    const key = `${bucket}:${itemId}`;
    if (itemId && bucket) {
      if (seen.has(key)) rowErrors.push("duplicate item_bucket + item_id");
      seen.add(key);
    }

    const price = entry.price && typeof entry.price === "object" ? entry.price : {};
    const denoms = ["gp", "sp", "cp"];
    const provided = denoms.filter((denom) => String(price[denom] ?? "").trim() !== "");
    if (!provided.length) rowErrors.push("price requires at least one denomination");
    provided.forEach((denom) => {
      const numeric = Number(price[denom]);
      if (!Number.isFinite(numeric) || numeric < 0 || !Number.isInteger(numeric)) {
        rowErrors.push(`price.${denom} must be a non-negative integer`);
      }
    });

    const stockLimitRaw = String(entry.stock_limit ?? "").trim();
    const stockSoldRaw = String(entry.stock_sold ?? "").trim();
    if (stockLimitRaw !== "") {
      const stockLimit = Number(stockLimitRaw);
      const stockSold = Number(stockSoldRaw === "" ? 0 : stockSoldRaw);
      if (!Number.isFinite(stockLimit) || stockLimit < 0 || !Number.isInteger(stockLimit)) {
        rowErrors.push("stock.limit must be a non-negative integer");
      }
      if (!Number.isFinite(stockSold) || stockSold < 0 || !Number.isInteger(stockSold)) {
        rowErrors.push("stock.sold must be a non-negative integer");
      } else if (Number.isFinite(stockLimit) && Number.isInteger(stockLimit) && stockSold > stockLimit) {
        rowErrors.push("stock.sold cannot exceed stock.limit");
      }
    } else if (stockSoldRaw !== "") {
      const stockSold = Number(stockSoldRaw);
      if (!Number.isFinite(stockSold) || stockSold < 0 || !Number.isInteger(stockSold)) {
        rowErrors.push("stock.sold must be a non-negative integer");
      }
    }

    if (rowErrors.length) errors[index] = rowErrors;
  });
  return errors;
};

const bindInput = (rowIndex, key, subkey = null) => (event) => {
  const row = state.entries[rowIndex];
  if (!row) return;
  if (subkey) {
    row[key] = row[key] || {};
    row[key][subkey] = event.target.value;
  } else if (event.target.type === "checkbox") {
    row[key] = Boolean(event.target.checked);
  } else {
    row[key] = event.target.value;
  }
  markDirty();
  state.rowErrors = localValidationErrors();
  updateCategorySuggestions();
  renderRows();
};

const deleteRow = (rowIndex) => {
  state.entries.splice(rowIndex, 1);
  markDirty();
  state.rowErrors = localValidationErrors();
  updateCategorySuggestions();
  renderRows();
};

const rowInput = ({ value = "", type = "text", onChange, min = null, invalid = false, title = "", list = "" }) => {
  const input = document.createElement("input");
  input.type = type;
  input.value = value;
  if (min !== null) input.min = String(min);
  if (list) input.setAttribute("list", list);
  if (invalid) {
    input.classList.add("invalid");
    if (title) input.title = title;
  }
  input.addEventListener("input", onChange);
  return input;
};

const rowSelect = ({ value = "", options = [], onChange, invalid = false, title = "" }) => {
  const select = document.createElement("select");
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select bucket";
  select.appendChild(placeholder);
  options.forEach((optionValue) => {
    const option = document.createElement("option");
    option.value = optionValue;
    option.textContent = optionValue;
    select.appendChild(option);
  });
  select.value = value || "";
  if (invalid) {
    select.classList.add("invalid");
    if (title) select.title = title;
  }
  select.addEventListener("input", onChange);
  return select;
};

const appendField = (container, { label, control, className = "" }) => {
  const field = document.createElement("label");
  field.className = `field ${className}`.trim();
  const text = document.createElement("span");
  text.className = "field-label";
  text.textContent = label;
  field.append(text, control);
  container.appendChild(field);
};

const updateCategorySuggestions = () => {
  if (!categorySuggestionsEl) return;
  const values = new Set(DEFAULT_CATEGORY_SUGGESTIONS);
  state.entries.forEach((entry) => {
    const category = String(entry.shop_category || "").trim();
    if (category) values.add(category);
  });
  categorySuggestionsEl.innerHTML = "";
  [...values].sort((a, b) => a.localeCompare(b)).forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    categorySuggestionsEl.appendChild(option);
  });
};

const renderRows = () => {
  rowsEl.innerHTML = "";
  state.entries.forEach((entry, index) => {
    const rowErrors = state.rowErrors[index] || [];
    const rowErrorText = rowErrors.join("; ");

    const invalidRequired = rowErrors.some((message) => message.includes("required") || message.includes("duplicate"));
    const invalidPrice = rowErrors.some((message) => message.includes("price"));
    const invalidStock = rowErrors.some((message) => message.includes("stock."));

    const stockLimit = toNumberOrUndefined(entry.stock_limit);
    const stockSold = Math.max(0, Number(toNumberOrUndefined(entry.stock_sold) ?? 0));
    const stockRemainingText = stockLimit === undefined
      ? "Unlimited"
      : String(Math.max(0, stockLimit - stockSold));

    const card = document.createElement("article");
    card.className = "catalog-card";
    if (rowErrors.length) {
      card.classList.add("row-invalid");
      card.title = rowErrorText;
    }

    const header = document.createElement("div");
    header.className = "card-header";

    const identity = document.createElement("div");
    identity.className = "identity";
    const readOnly = entry._readonly || {};
    const nameEl = document.createElement("h3");
    nameEl.textContent = readOnly.name || entry.item_id || "New catalog entry";
    const identityMeta = document.createElement("p");
    identityMeta.className = "identity-meta";
    identityMeta.textContent = readOnly.type || "Item definition";
    identity.append(nameEl, identityMeta);

    const enabledLabel = document.createElement("label");
    enabledLabel.className = "toggle";
    const enabledInput = document.createElement("input");
    enabledInput.type = "checkbox";
    enabledInput.checked = entry.enabled !== false;
    enabledInput.addEventListener("input", bindInput(index, "enabled"));
    const toggleUi = document.createElement("span");
    toggleUi.className = "toggle-ui";
    const toggleText = document.createElement("span");
    toggleText.className = "toggle-text";
    toggleText.textContent = enabledInput.checked ? "Enabled" : "Disabled";
    enabledInput.addEventListener("input", () => {
      toggleText.textContent = enabledInput.checked ? "Enabled" : "Disabled";
    });
    enabledLabel.append(enabledInput, toggleUi, toggleText);

    header.append(identity, enabledLabel);

    const body = document.createElement("div");
    body.className = "card-body";

    const primaryGroup = document.createElement("section");
    primaryGroup.className = "group group-primary";
    const primaryTitle = document.createElement("h4");
    primaryTitle.textContent = "Identity";
    primaryGroup.appendChild(primaryTitle);

    appendField(primaryGroup, {
      label: "Item ID",
      control: rowInput({ value: entry.item_id || "", onChange: bindInput(index, "item_id"), invalid: invalidRequired, title: rowErrorText }),
    });
    appendField(primaryGroup, {
      label: "Bucket",
      control: rowSelect({ value: entry.item_bucket || "", options: ITEM_BUCKET_OPTIONS, onChange: bindInput(index, "item_bucket"), invalid: invalidRequired, title: rowErrorText }),
    });
    appendField(primaryGroup, {
      label: "Category",
      control: rowInput({ value: entry.shop_category || "", onChange: bindInput(index, "shop_category"), invalid: invalidRequired, title: rowErrorText, list: "shop-category-suggestions" }),
    });

    const priceGroup = document.createElement("section");
    priceGroup.className = "group group-price";
    const priceTitle = document.createElement("h4");
    priceTitle.textContent = "Price";
    priceGroup.appendChild(priceTitle);
    const priceGrid = document.createElement("div");
    priceGrid.className = "price-grid";
    ["gp", "sp", "cp"].forEach((denom) => {
      appendField(priceGrid, {
        label: denom,
        className: "compact",
        control: rowInput({
          value: entry.price?.[denom] ?? "",
          type: "number",
          min: 0,
          onChange: bindInput(index, "price", denom),
          invalid: invalidPrice,
          title: rowErrorText,
        }),
      });
    });
    priceGroup.appendChild(priceGrid);

    const stockGroup = document.createElement("section");
    stockGroup.className = "group group-stock";
    const stockTitle = document.createElement("h4");
    stockTitle.textContent = "Stock";
    stockGroup.appendChild(stockTitle);
    const stockGrid = document.createElement("div");
    stockGrid.className = "stock-grid";
    appendField(stockGrid, {
      label: "Limit",
      className: "compact",
      control: rowInput({ value: entry.stock_limit ?? "", type: "number", min: 0, onChange: bindInput(index, "stock_limit"), invalid: invalidStock, title: rowErrorText }),
    });
    appendField(stockGrid, {
      label: "Sold",
      className: "compact",
      control: rowInput({ value: entry.stock_sold ?? 0, type: "number", min: 0, onChange: bindInput(index, "stock_sold"), invalid: invalidStock, title: rowErrorText }),
    });
    const stockRemaining = document.createElement("div");
    stockRemaining.className = "stock-remaining-wrap";
    const stockRemainingLabel = document.createElement("span");
    stockRemainingLabel.className = "field-label";
    stockRemainingLabel.textContent = "Remaining";
    const stockBadge = document.createElement("span");
    stockBadge.className = "stock-remaining";
    if (stockRemainingText === "Unlimited") stockBadge.classList.add("unlimited");
    if (stockRemainingText === "0") stockBadge.classList.add("sold-out");
    stockBadge.textContent = stockRemainingText;
    stockRemaining.append(stockRemainingLabel, stockBadge);
    stockGrid.appendChild(stockRemaining);
    stockGroup.appendChild(stockGrid);

    const metadata = document.createElement("details");
    metadata.className = "group metadata";
    const summary = document.createElement("summary");
    summary.textContent = "Definition metadata";
    const definition = document.createElement("p");
    definition.innerHTML = `<strong>Source:</strong> ${readOnly.definition_path || "—"}`;
    const type = document.createElement("p");
    type.innerHTML = `<strong>Type:</strong> ${readOnly.type || "—"}`;
    metadata.append(summary, type, definition);

    const footer = document.createElement("div");
    footer.className = "card-footer";
    const rowNumber = document.createElement("p");
    rowNumber.className = "row-index";
    rowNumber.textContent = `Entry #${index + 1}`;
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "row-delete";
    deleteButton.textContent = "Delete entry";
    deleteButton.addEventListener("click", () => deleteRow(index));
    footer.append(rowNumber, deleteButton);

    body.append(primaryGroup, priceGroup, stockGroup, metadata);
    card.append(header, body, footer);

    if (rowErrors.length) {
      const error = document.createElement("p");
      error.className = "row-error";
      error.textContent = `Row ${index + 1}: ${rowErrorText}`;
      card.appendChild(error);
    }

    rowsEl.appendChild(card);
  });
};

const renderWealth = () => {
  wealthRowsEl.innerHTML = "";
  state.wealthPlayers.forEach((player) => {
    const tr = document.createElement("tr");
    const currency = player.currency || {};
    [player.name || "—", Number(currency.gp || 0), Number(currency.sp || 0), Number(currency.cp || 0), Number(player.total_cp || 0)].forEach((value) => {
      const td = document.createElement("td");
      td.textContent = String(value);
      tr.appendChild(td);
    });
    wealthRowsEl.appendChild(tr);
  });
  const party = state.wealthPartyCurrency || { gp: 0, sp: 0, cp: 0 };
  partyTotalGpEl.textContent = String(Number(party.gp || 0));
  partyTotalSpEl.textContent = String(Number(party.sp || 0));
  partyTotalCpEl.textContent = String(Number(party.cp || 0));
  partyTotalCpValueEl.textContent = String(Number(state.wealthPartyTotalCp || 0));
};

const loadWealth = async () => {
  wealthSummaryStatusEl.textContent = "Loading player wealth…";
  try {
    const payload = await fetchJson("/api/shop/admin/player-wealth");
    state.wealthPlayers = Array.isArray(payload.players) ? payload.players : [];
    state.wealthPartyCurrency = payload.party_total_currency || { gp: 0, sp: 0, cp: 0 };
    state.wealthPartyTotalCp = Number(payload.party_total_cp || 0);
    wealthSummaryStatusEl.textContent = `Loaded ${state.wealthPlayers.length} players.`;
  } catch (error) {
    state.wealthPlayers = [];
    state.wealthPartyCurrency = { gp: 0, sp: 0, cp: 0 };
    state.wealthPartyTotalCp = 0;
    wealthSummaryStatusEl.textContent = `Failed to load player wealth: ${error.message}`;
  }
  renderWealth();
};

const normalizeFromResponse = (payload, { markClean = false } = {}) => {
  state.formatVersion = Number(payload?.format_version || 1);
  state.entries = (Array.isArray(payload?.entries) ? payload.entries : []).map((entry) => editableFromNormalized(entry));
  const revision = payload?.revision;
  state.revision = revision ? String(revision) : state.revision;
  state.rowErrors = localValidationErrors();
  updateCategorySuggestions();
  if (markClean) {
    state.dirty = false;
    updateDirtyState();
  }
  renderRows();
};

const summarizeRowErrors = (errors) => Object.entries(errors)
  .map(([index, issues]) => `Row ${Number(index) + 1}: ${(issues || []).join(", ")}`)
  .join(" | ");

const loadCatalog = async () => {
  if (state.dirty) {
    const proceed = window.confirm("You have unsaved catalog edits. Reload and discard local changes?");
    if (!proceed) return;
  }
  setBusy(true);
  setStatus("Loading catalog from /api/shop/catalog?include_disabled=true ...", "info");
  try {
    const payload = await fetchJson("/api/shop/catalog?include_disabled=true");
    normalizeFromResponse({ format_version: 1, entries: payload.entries || [], revision: payload.revision }, { markClean: true });
    await loadWealth();
    setStatus(`Loaded ${state.entries.length} catalog entr${state.entries.length === 1 ? "y" : "ies"}.`, "ok");
  } catch (error) {
    setStatus(`Load failed: ${error.message}`, "error");
  } finally {
    setBusy(false);
  }
};

const validateCatalog = async () => {
  state.rowErrors = localValidationErrors();
  renderRows();
  if (Object.keys(state.rowErrors).length) {
    setStatus(`Fix local validation errors before backend validate: ${summarizeRowErrors(state.rowErrors)}`, "error");
    return;
  }
  setBusy(true);
  setStatus("Validating catalog with backend validator...", "info");
  try {
    const validated = await fetchJson("/api/shop/catalog/validate", { method: "POST", body: JSON.stringify(buildPayload()) });
    normalizeFromResponse(validated);
    setStatus(`Validation passed. ${state.entries.length} entries normalized.`, "ok");
  } catch (error) {
    setStatus(`Validation failed: ${error.message}`, "error");
  } finally {
    setBusy(false);
  }
};

const saveCatalog = async () => {
  state.rowErrors = localValidationErrors();
  renderRows();
  if (Object.keys(state.rowErrors).length) {
    setStatus(`Fix local validation errors before save: ${summarizeRowErrors(state.rowErrors)}`, "error");
    return;
  }
  setBusy(true);
  setStatus("Saving catalog...", "info");
  try {
    const saved = await fetchJson("/api/shop/catalog", { method: "PUT", body: JSON.stringify(buildPayload()) });
    normalizeFromResponse(saved, { markClean: true });
    await loadWealth();
    setStatus(`Save successful. ${state.entries.length} entries saved.`, "ok");
  } catch (error) {
    if (error.status === 409) {
      setStatus("Save blocked: catalog changed on host. Reload the latest catalog and retry.", "error");
    } else {
      setStatus(`Save failed: ${error.message}`, "error");
    }
  } finally {
    setBusy(false);
  }
};

const addEntry = () => {
  state.entries.push(editableFromNormalized({ item_id: "", item_bucket: "", shop_category: "", enabled: true, price: { gp: 0 }, stock_sold: 0 }));
  markDirty();
  state.rowErrors = localValidationErrors();
  updateCategorySuggestions();
  renderRows();
  setStatus(`Added entry row. Total rows: ${state.entries.length}.`, "info");
};

const warnOnUnload = (event) => {
  if (!state.dirty) return undefined;
  event.preventDefault();
  event.returnValue = "You have unsaved shop catalog changes.";
  return event.returnValue;
};

const init = async () => {
  assertRequiredElements();
  updateDirtyState();
  updateCategorySuggestions();
  reloadButton.addEventListener("click", loadCatalog);
  addRowButton.addEventListener("click", addEntry);
  validateButton.addEventListener("click", validateCatalog);
  saveButton.addEventListener("click", saveCatalog);
  window.addEventListener("beforeunload", warnOnUnload);
  await loadCatalog();
};

init().catch((error) => {
  setStatus(`Shop admin failed to start: ${error.message}`, "error");
});
