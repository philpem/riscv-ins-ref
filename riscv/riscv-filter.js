(() => {
  "use strict";

  const container = document.querySelector(".listing-filter");
  if (!container) return;

  const table = container.nextElementSibling;
  if (!table || table.tagName !== "TABLE") return;

  const rows = Array.from(table.tBodies[0]?.rows ?? []);
  const label = container.dataset.filterLabel || "entries";
  const extensions = new Set();
  const prefixes = new Set();

  for (const row of rows) {
    for (const value of (row.dataset.extensions || "").split(/\s+/)) {
      if (value) extensions.add(value);
    }
    if (row.dataset.prefix) prefixes.add(row.dataset.prefix);
  }

  const options = [
    ...Array.from(extensions)
      .sort()
      .map((value) => ({ value, label: value })),
    ...Array.from(prefixes)
      .sort()
      .map((value) => ({ value, label: `${value}*` })),
  ];
  if (options.length === 0) return;

  const known = new Set(options.map((option) => option.value));
  const url = new URL(window.location.href);
  const storageKey = "riscv-listing-filter";
  let stored = null;
  try {
    stored = JSON.parse(window.localStorage.getItem(storageKey) || "null");
  } catch (error) {
    stored = null;
  }

  const requested = url.searchParams.get("ext");
  let selected = new Set(
    requested
      ? requested.split(",")
      : Array.isArray(stored)
        ? stored
        : options.map((option) => option.value),
  );
  selected = new Set(Array.from(selected).filter((value) => known.has(value)));

  const controls = container.querySelector(".listing-filter-controls");
  const status = container.querySelector(".listing-filter-status");

  const actions = document.createElement("div");
  actions.className = "listing-filter-actions";

  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.textContent = "All";

  const noneButton = document.createElement("button");
  noneButton.type = "button";
  noneButton.textContent = "None";

  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "Find an extension";
  search.setAttribute("aria-label", "Find an extension");

  actions.append(allButton, noneButton, search);

  const details = document.createElement("details");
  details.className = "listing-filter-options";
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent = "Extensions";
  const grid = document.createElement("div");
  grid.className = "listing-filter-grid";
  details.append(summary, grid);

  const boxes = new Map();
  for (const option of options) {
    const id = `filter-${option.value.replace(/[^A-Za-z0-9_-]/g, "-")}`;
    const optionLabel = document.createElement("label");
    optionLabel.htmlFor = id;
    optionLabel.dataset.filterText = option.value.toLowerCase();
    const box = document.createElement("input");
    box.type = "checkbox";
    box.id = id;
    box.value = option.value;
    const text = document.createElement("span");
    text.textContent = option.label;
    optionLabel.append(box, text);
    grid.appendChild(optionLabel);
    boxes.set(option.value, box);
  }

  controls.append(actions, details);

  const apply = () => {
    let shown = 0;
    for (const row of rows) {
      const tokens = (row.dataset.extensions || "").split(/\s+/).filter(Boolean);
      const prefix = row.dataset.prefix || "";
      const match =
        selected.size > 0 &&
        (tokens.some((token) => selected.has(token)) ||
          (prefix && selected.has(prefix)));
      row.hidden = !match;
      if (match) shown += 1;
    }
    status.textContent = `Showing ${shown} of ${rows.length} ${label}`;
    for (const [value, box] of boxes) box.checked = selected.has(value);
    const values = Array.from(selected).sort();
    if (values.length > 0 && values.length < options.length) {
      url.searchParams.set("ext", values.join(","));
    } else {
      url.searchParams.delete("ext");
    }
    window.history.replaceState(null, "", url);
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(values));
    } catch (error) {
      /* Storage can be unavailable in private browsing. */
    }
  };

  for (const [value, box] of boxes) {
    box.addEventListener("change", () => {
      if (box.checked) selected.add(value);
      else selected.delete(value);
      apply();
    });
  }

  allButton.addEventListener("click", () => {
    selected = new Set(options.map((option) => option.value));
    apply();
  });

  noneButton.addEventListener("click", () => {
    selected = new Set();
    apply();
  });

  search.addEventListener("input", () => {
    const query = search.value.trim().toLowerCase();
    for (const optionLabel of grid.children) {
      optionLabel.hidden =
        Boolean(query) && !optionLabel.dataset.filterText.includes(query);
    }
  });

  apply();
})();
