const filterRows = document.getElementById("filter-rows");
if (filterRows) {
  const kinds = JSON.parse(document.getElementById("filter-kinds").textContent);
  const total = document.getElementById("id_filters-TOTAL_FORMS");
  const add = document.getElementById("add-filter");
  function initialize(row) {
    const property = row.querySelector('select[name$="-property"]');
    function updateKind() {
      row.querySelectorAll("[data-filter-kind]").forEach((group) => {
        const active = group.dataset.filterKind === kinds[property.value];
        group.hidden = !active;
        // Ignore stale values after switching the property to a different type.
        group.querySelectorAll("input, select").forEach((input) => { input.disabled = !active; });
      });
    }
    property.addEventListener("change", updateKind);
    row.querySelector("[data-remove-filter]").addEventListener("click", () => {
      row.remove();
      [...filterRows.children].forEach((remaining, index) => {
        remaining.querySelectorAll("[name], [id], label[for]").forEach((element) => {
          ["name", "id", "for", "aria-describedby"].forEach((attribute) => {
            if (element.hasAttribute(attribute)) element.setAttribute(attribute,
              element.getAttribute(attribute).replace(/filters-\d+-/g, `filters-${index}-`));
          });
        });
      });
      total.value = filterRows.children.length;
      add.disabled = false;
    });
    updateKind();
  }
  [...filterRows.children].forEach(initialize);
  add.addEventListener("click", () => {
    if (filterRows.children.length >= 20) return;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = document.getElementById("empty-filter").innerHTML.replaceAll("__prefix__", total.value);
    const row = wrapper.firstElementChild;
    filterRows.append(row);
    total.value = filterRows.children.length;
    initialize(row);
    add.disabled = filterRows.children.length >= 20;
  });
}
