const rowsEl = document.getElementById("catalog-rows");
const statusEl = document.getElementById("status-banner");
const reloadButton = document.getElementById("reload-button");
const addRowButton = document.getElementById("add-row-button");
const validateButton = document.getElementById("validate-button");
const saveButton = document.getElementById("save-button");

const REQUIRED_IDS = [
  "catalog-rows",
  "status-banner",
  "reload-button",
  "add-row-button",
  "validate-button",
  "save-button",
];

const assertRequiredElements = () => {
  const missing = REQUIRED_IDS.filter((id) => !document.getElementById(id));
  if (!missing.length) {
    return;
  }
  throw new Error(`Shop admin template missing required IDs: ${missing.join(", ")}`);
};

const state = {
  formatVersion: 1,
  entries: [],
  busy: false,
};

const setStatus = (message, tone = "info") => {
  statusEl.textContent = message;
  statusEl.classList.remove("ok", "error", "info");
  statusEl.classList.add(tone);
};

const toNumberOrUndefined = (value) => {
  if (value === "" || value === null || value === undefined) {
    return undefined;
  }
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
  _readonly: {
    name: entry.name || "",
    type: entry.type || "",
    definition_path: entry.definition_path || "",
  },
});

const buildPayload = () => ({
  format_version: Number(state.formatVersion || 1),
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
    return payloadEntry;
  }),
});

const setBusy = (busy) => {
  state.busy = Boolean(busy);
  [reloadButton, addRowButton, validateButton, saveButton].forEach((button) => {
    button.disabled = state.busy;
  });
  rowsEl.querySelectorAll("input,button").forEach((el) => {
    el.disabled = state.busy;
  });
};

const bindInput = (rowIndex, key, subkey = null) => (event) => {
  const row = state.entries[rowIndex];
  if (!row) {
    return;
  }
  if (subkey) {
    row[key] = row[key] || {};
    row[key][subkey] = event.target.value;
  } else if (event.target.type === "checkbox") {
    row[key] = Boolean(event.target.checked);
  } else {
    row[key] = event.target.value;
  }
};

const deleteRow = (rowIndex) => {
  state.entries.splice(rowIndex, 1);
  renderRows();
};

const rowInput = ({ value = "", type = "text", onChange, min = null }) => {
  const input = document.createElement("input");
  input.type = type;
  input.value = value;
  if (min !== null) {
    input.min = String(min);
  }
  input.addEventListener("input", onChange);
  return input;
};

const renderRows = () => {
  rowsEl.innerHTML = "";
  state.entries.forEach((entry, index) => {
    const tr = document.createElement("tr");
    const readOnly = entry._readonly || {};

    const fields = [
      rowInput({ value: entry.item_id || "", onChange: bindInput(index, "item_id") }),
      rowInput({ value: entry.item_bucket || "", onChange: bindInput(index, "item_bucket") }),
      rowInput({ value: entry.shop_category || "", onChange: bindInput(index, "shop_category") }),
      (() => {
        const checkbox = rowInput({ type: "checkbox", onChange: bindInput(index, "enabled") });
        checkbox.checked = entry.enabled !== false;
        return checkbox;
      })(),
      rowInput({ value: entry.price?.gp ?? "", type: "number", min: 0, onChange: bindInput(index, "price", "gp") }),
      rowInput({ value: entry.price?.sp ?? "", type: "number", min: 0, onChange: bindInput(index, "price", "sp") }),
      rowInput({ value: entry.price?.cp ?? "", type: "number", min: 0, onChange: bindInput(index, "price", "cp") }),
      (() => {
        const span = document.createElement("span");
        span.className = "read-only";
        span.textContent = readOnly.name || "—";
        return span;
      })(),
      (() => {
        const span = document.createElement("span");
        span.className = "read-only";
        span.textContent = readOnly.type || "—";
        return span;
      })(),
      (() => {
        const span = document.createElement("span");
        span.className = "read-only";
        span.textContent = readOnly.definition_path || "—";
        return span;
      })(),
      (() => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "row-delete";
        button.textContent = "Delete";
        button.addEventListener("click", () => deleteRow(index));
        return button;
      })(),
    ];

    fields.forEach((fieldEl) => {
      const td = document.createElement("td");
      td.appendChild(fieldEl);
      tr.appendChild(td);
    });

    rowsEl.appendChild(tr);
  });
};

const normalizeFromResponse = (payload) => {
  state.formatVersion = Number(payload?.format_version || 1);
  const entries = Array.isArray(payload?.entries) ? payload.entries : [];
  state.entries = entries.map((entry) => editableFromNormalized(entry));
  renderRows();
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
    const detail = body && body.detail ? String(body.detail) : `${response.status} ${response.statusText}`;
    throw new Error(detail);
  }
  return body || {};
};

const loadCatalog = async () => {
  setBusy(true);
  setStatus("Loading catalog from /api/shop/catalog?include_disabled=true ...", "info");
  try {
    const payload = await fetchJson("/api/shop/catalog?include_disabled=true");
    normalizeFromResponse({ format_version: 1, entries: payload.entries || [] });
    setStatus(`Loaded ${state.entries.length} catalog entr${state.entries.length === 1 ? "y" : "ies"}.`, "ok");
  } catch (error) {
    setStatus(`Load failed: ${error.message}`, "error");
  } finally {
    setBusy(false);
  }
};

const validateCatalog = async () => {
  setBusy(true);
  setStatus("Validating catalog with backend validator...", "info");
  try {
    const payload = buildPayload();
    const validated = await fetchJson("/api/shop/catalog/validate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    normalizeFromResponse(validated);
    setStatus(`Validation passed. ${state.entries.length} entries normalized.`, "ok");
  } catch (error) {
    setStatus(`Validation failed: ${error.message}`, "error");
  } finally {
    setBusy(false);
  }
};

const saveCatalog = async () => {
  setBusy(true);
  setStatus("Saving catalog...", "info");
  try {
    const payload = buildPayload();
    const saved = await fetchJson("/api/shop/catalog", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    normalizeFromResponse(saved);
    setStatus(`Save successful. ${state.entries.length} entries saved.`, "ok");
  } catch (error) {
    setStatus(`Save failed: ${error.message}`, "error");
  } finally {
    setBusy(false);
  }
};

const addEntry = () => {
  state.entries.push(
    editableFromNormalized({
      item_id: "",
      item_bucket: "",
      shop_category: "",
      enabled: true,
      price: { gp: 0 },
    }),
  );
  renderRows();
  setStatus(`Added entry row. Total rows: ${state.entries.length}.`, "info");
};

const init = async () => {
  assertRequiredElements();
  reloadButton.addEventListener("click", loadCatalog);
  addRowButton.addEventListener("click", addEntry);
  validateButton.addEventListener("click", validateCatalog);
  saveButton.addEventListener("click", saveCatalog);
  await loadCatalog();
};

init().catch((error) => {
  setStatus(`Shop admin failed to start: ${error.message}`, "error");
});
