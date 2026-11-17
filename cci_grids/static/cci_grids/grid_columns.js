// Only preferences are stored in this browser; scientific records are untouched.
document.querySelectorAll("[data-registry-table]").forEach((table) => {
  const controls = [...table.querySelectorAll("[data-column-toggle]")];
  const defaults = controls.filter((control) => control.dataset.default === "true")
    .map((control) => control.dataset.columnToggle);
  const storageKey = table.dataset.preferenceKey;
  let selected = defaults;
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    if (Array.isArray(saved) && saved.every((key) => typeof key === "string")) {
      selected = saved;
    }
  } catch (_) { /* Storage may be unavailable; default columns still work. */ }

  function apply(keys) {
    const shown = new Set(keys);
    controls.forEach((control) => { control.checked = shown.has(control.dataset.columnToggle); });
    table.querySelectorAll("[data-column]").forEach((cell) => {
      cell.hidden = !shown.has(cell.dataset.column);
    });
  }
  function save() {
    const keys = controls.filter((control) => control.checked).map((control) => control.dataset.columnToggle);
    apply(keys);
    try { localStorage.setItem(storageKey, JSON.stringify(keys)); } catch (_) { /* Optional preference. */ }
  }
  controls.forEach((control) => control.addEventListener("change", save));
  table.querySelector("[data-columns-all]").addEventListener("click", () => {
    controls.forEach((control) => { control.checked = true; }); save();
  });
  table.querySelector("[data-columns-default]").addEventListener("click", () => { apply(defaults); save(); });
  apply(selected);
});
