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

const storageRows = document.getElementById('storage-rows');
if (storageRows) {
  const total = document.getElementById('id_storage-TOTAL_FORMS');
  const add = document.getElementById('add-storage-filter');
  function narrowStorageChoices() {
    const values = {puck: [], box: [], box_type: []};
    [...storageRows.children].forEach(row => {
      const key = row.querySelector('select[name$="-property"]').value;
      if (key in values) {
        const select = row.querySelector(`select[name$="-${key}"]`);
        if (select.value) values[key].push(select.value);
      }
    });
    storageRows.querySelectorAll('select[name$="-box"]').forEach(select => {
      [...select.options].forEach(option => {
        const allowed = !option.value || (values.puck.every(id => id === option.dataset.puck)
          && values.box_type.every(id => id === option.dataset.type));
        option.hidden = !allowed;
        option.disabled = !allowed;
        if (!allowed && option.selected) select.value = '';
      });
    });
    const boxes = [...storageRows.children].filter(row => row.querySelector('select[name$="-property"]').value === 'box')
      .map(row => row.querySelector('select[name$="-box"]').value).filter(Boolean);
    storageRows.querySelectorAll('select[name$="-slot"]').forEach(select => {
      [...select.options].forEach(option => {
        const allowed = !option.value || boxes.every(id => id === option.dataset.box);
        option.hidden = !allowed;
        option.disabled = !allowed;
        if (!allowed && option.selected) select.value = '';
      });
    });
  }
  storageRows.addEventListener('change', narrowStorageChoices);
  function initializeStorage(row) {
    const property = row.querySelector('select[name$="-property"]');
    function update() {
      row.querySelectorAll('[data-storage-kind]').forEach(group => {
        const active = group.dataset.storageKind === property.value;
        group.hidden = !active;
        group.querySelectorAll('select').forEach(input => { input.disabled = !active; });
      });
    }
    property.addEventListener('change', update);
    row.querySelector('[data-remove-filter]').addEventListener('click', () => {
      row.remove();
      [...storageRows.children].forEach((remaining, index) => {
        remaining.querySelectorAll('[name], [id], label[for]').forEach(element => {
          ['name', 'id', 'for', 'aria-describedby'].forEach(attribute => {
            if (element.hasAttribute(attribute)) element.setAttribute(attribute,
              element.getAttribute(attribute).replace(/storage-\d+-/g, `storage-${index}-`));
          });
        });
      });
      total.value = storageRows.children.length;
      add.disabled = false;
      narrowStorageChoices();
    });
    update();
  }
  [...storageRows.children].forEach(initializeStorage);
  narrowStorageChoices();
  add.addEventListener('click', () => {
    if (storageRows.children.length >= 20) return;
    const wrapper = document.createElement('div');
    wrapper.innerHTML = document.getElementById('empty-storage-filter').innerHTML.replaceAll('__prefix__', total.value);
    const row = wrapper.firstElementChild;
    storageRows.append(row);
    total.value = storageRows.children.length;
    initializeStorage(row);
    narrowStorageChoices();
    add.disabled = storageRows.children.length >= 20;
  });
}
