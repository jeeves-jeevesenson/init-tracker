const rowsEl = document.getElementById("catalog-rows");
const statusEl = document.getElementById("status-banner");
const reloadButton = document.getElementById("reload-button");
const addRowButton = document.getElementById("add-row-button");
const validateButton = document.getElementById("validate-button");
const saveButton = document.getElementById("save-button");
const dirtyStateEl = document.getElementById("dirty-state");

const REQUIRED_IDS = [
  "catalog-rows",
  "status-banner",
  "reload-button",
  "add-row-button",
  "validate-button",
  "save-button",
  "dirty-state",
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
  dirty: false,
  revision: null,
  rowErrors: {},
};

const setStatus = (message, tone = "info") => {
  statusEl.textContent = message;
  statusEl.classList.remove("ok", "error", "info");
  statusEl.classList.add(tone);
};

const updateDirtyState = () => {
  if (!dirtyStateEl) {
    return;
  }
  dirtyStateEl.textContent = state.dirty ? "Unsaved changes" : "All changes saved";
  dirtyStateEl.classList.toggle("dirty", state.dirty);
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
  if (!response.ok) {
    throw parseErrorDetail(body, response);
  }
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
    if (!provided.length) {
      rowErrors.push("price requires at least one denomination");
    }
    provided.forEach((denom) => {
      const numeric = Number(price[denom]);
      if (!Number.isFinite(numeric) || numeric < 0 || !Number.isInteger(numeric)) {
        rowErrors.push(`price.${denom} must be a non-negative integer`);
      }
    });
    if (rowErrors.length) {
      errors[index] = rowErrors;
    }
  });
  return errors;
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
  markDirty();
  state.rowErrors = localValidationErrors();
  renderRows();
};

const deleteRow = (rowIndex) => {
  state.entries.splice(rowIndex, 1);
  markDirty();
  state.rowErrors = localValidationErrors();
  renderRows();
};

const rowInput = ({ value = "", type = "text", onChange, min = null, invalid = false, title = "" }) => {
  const input = document.createElement("input");
  input.type = type;
  input.value = value;
  if (min !== null) {
    input.min = String(min);
  }
  if (invalid) {
    input.classList.add("invalid");
    if (title) input.title = title;
  }
  input.addEventListener("input", onChange);
  return input;
};

const renderRows = () => {
  rowsEl.innerHTML = "";
  state.entries.forEach((entry, index) => {
    const tr = document.createElement("tr");
    const readOnly = entry._readonly || {};
    const rowErrors = state.rowErrors[index] || [];
    const rowErrorText = rowErrors.join("; ");
    if (rowErrors.length) {
      tr.classList.add("row-invalid");
      tr.title = rowErrorText;
    }

    const invalidRequired = rowErrors.some((message) => message.includes("required") || message.includes("duplicate"));
    const invalidPrice = rowErrors.some((message) => message.includes("price"));

    const fields = [
      rowInput({ value: entry.item_id || "", onChange: bindInput(index, "item_id"), invalid: invalidRequired, title: rowErrorText }),
      rowInput({ value: entry.item_bucket || "", onChange: bindInput(index, "item_bucket"), invalid: invalidRequired, title: rowErrorText }),
      rowInput({ value: entry.shop_category || "", onChange: bindInput(index, "shop_category"), invalid: invalidRequired, title: rowErrorText }),
      (() => {
        const checkbox = rowInput({ type: "checkbox", onChange: bindInput(index, "enabled") });
        checkbox.checked = entry.enabled !== false;
        return checkbox;
      })(),
      rowInput({ value: entry.price?.gp ?? "", type: "number", min: 0, onChange: bindInput(index, "price", "gp"), invalid: invalidPrice, title: rowErrorText }),
      rowInput({ value: entry.price?.sp ?? "", type: "number", min: 0, onChange: bindInput(index, "price", "sp"), invalid: invalidPrice, title: rowErrorText }),
      rowInput({ value: entry.price?.cp ?? "", type: "number", min: 0, onChange: bindInput(index, "price", "cp"), invalid: invalidPrice, title: rowErrorText }),
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

    if (rowErrors.length) {
      const errorRow = document.createElement("tr");
      errorRow.className = "row-error";
      const cell = document.createElement("td");
      cell.colSpan = 11;
      cell.textContent = `Row ${index + 1}: ${rowErrorText}`;
      errorRow.appendChild(cell);
      rowsEl.appendChild(tr);
      rowsEl.appendChild(errorRow);
      return;
    }
    rowsEl.appendChild(tr);
  });
};

const normalizeFromResponse = (payload, { markClean = false } = {}) => {
  state.formatVersion = Number(payload?.format_version || 1);
  const entries = Array.isArray(payload?.entries) ? payload.entries : [];
  state.entries = entries.map((entry) => editableFromNormalized(entry));
  const revision = payload?.revision;
  state.revision = revision ? String(revision) : state.revision;
  state.rowErrors = localValidationErrors();
  if (markClean) {
    state.dirty = false;
    updateDirtyState();
  }
  renderRows();
};

const summarizeRowErrors = (errors) => {
  const rows = Object.keys(errors).length;
  if (!rows) {
    return "";
  }
  return Object.entries(errors)
    .map(([index, issues]) => `Row ${Number(index) + 1}: ${(issues || []).join(", ")}`)
    .join(" | ");
};

const loadCatalog = async () => {
  if (state.dirty) {
    const proceed = window.confirm("You have unsaved catalog edits. Reload and discard local changes?");
    if (!proceed) {
      return;
    }
  }
  setBusy(true);
  setStatus("Loading catalog from /api/shop/catalog?include_disabled=true ...", "info");
  try {
    const payload = await fetchJson("/api/shop/catalog?include_disabled=true");
    normalizeFromResponse({ format_version: 1, entries: payload.entries || [], revision: payload.revision }, { markClean: true });
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
  state.rowErrors = localValidationErrors();
  renderRows();
  if (Object.keys(state.rowErrors).length) {
    setStatus(`Fix local validation errors before save: ${summarizeRowErrors(state.rowErrors)}`, "error");
    return;
  }
  setBusy(true);
  setStatus("Saving catalog...", "info");
  try {
    const payload = buildPayload();
    const saved = await fetchJson("/api/shop/catalog", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    normalizeFromResponse(saved, { markClean: true });
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
  state.entries.push(
    editableFromNormalized({
      item_id: "",
      item_bucket: "",
      shop_category: "",
      enabled: true,
      price: { gp: 0 },
    }),
  );
  markDirty();
  state.rowErrors = localValidationErrors();
  renderRows();
  setStatus(`Added entry row. Total rows: ${state.entries.length}.`, "info");
};

const warnOnUnload = (event) => {
  if (!state.dirty) {
    return undefined;
  }
  event.preventDefault();
  event.returnValue = "You have unsaved shop catalog changes.";
  return event.returnValue;
};

const init = async () => {
  assertRequiredElements();
  updateDirtyState();
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
