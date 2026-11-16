const inlineStorage = document.querySelector('[data-inline-storage]');
if (inlineStorage) {
  const panel = inlineStorage.querySelector('[data-storage-panel]');
  const status = inlineStorage.querySelector('[data-storage-status]');
  const properties = document.getElementById('grid-properties');
  document.querySelector('a[href="#storage-actions"]')?.addEventListener('click', () => {
    document.getElementById('storage-actions').open = true;
  });
  const preparation = document.getElementById('grid-preparation-form');
  const version = preparation.elements.namedItem('expected_version');
  const clipped = preparation.elements.namedItem('is_clipped');
  const snapshot = () => JSON.stringify([...new FormData(preparation)]);
  let saved = snapshot();
  let busy = false;
  let stale = false;

  document.getElementById('grid-outcome-form')?.addEventListener('submit', event => {
    if (snapshot() !== saved && !window.confirm('You have unsaved preparation changes. Continue and discard those changes?')) event.preventDefault();
  });
  document.getElementById('grid-correction-form')?.addEventListener('submit', event => {
    if (snapshot() !== saved && !window.confirm('You have unsaved preparation changes. Continue and discard those changes?')) event.preventDefault();
  });
  const outcomeForm = document.getElementById('grid-outcome-form');
  if (outcomeForm) {
    const outcome = outcomeForm.elements.namedItem('outcome');
    const reason = outcomeForm.elements.namedItem('reason');
    const defaultReason = 'Imaged but not recovered';
    outcome.addEventListener('change', () => {
      if (outcome.value === 'screened_discarded' && !reason.value.trim()) reason.value = defaultReason;
      else if (outcome.value !== 'screened_discarded' && reason.value === defaultReason) reason.value = '';
    });
  }

  async function load(url, options = {}, placing = false) {
    if (busy) return;
    busy = true;
    properties.inert = true;
    inlineStorage.setAttribute('aria-busy', 'true');
    status.textContent = 'Loading storage actions…';
    try {
      const response = await fetch(url, {...options, credentials: 'same-origin'});
      if (!response.ok) throw new Error('Storage actions could not be loaded.');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      const content = parsed.querySelector('[data-storage-content]');
      if (!content) throw new Error('Please refresh the page and sign in again if needed.');
      if (placing && content.dataset.placed === '1') {
        version.value = content.dataset.version;
        const outcomeVersion = document.querySelector('#grid-outcome-form [name="expected_version"]');
        if (outcomeVersion) outcomeVersion.value = content.dataset.version;
        const gridStatus = document.querySelector('[data-grid-status]');
        if (gridStatus && gridStatus.textContent === 'Unknown — needs review') gridStatus.textContent = 'In storage';
        clipped.checked = content.dataset.clipped === '1';
        document.querySelector('[data-grid-clipping-label]').textContent = clipped.checked ? 'Clipped' : 'Unclipped';
        saved = snapshot();
        status.textContent = 'Placement saved.';
      } else {
        stale = content.dataset.version !== version.value;
        status.textContent = stale ? 'This grid changed. Refresh before editing or storing it.' : '';
      }
      panel.replaceChildren(content);
    } catch (error) {
      status.textContent = error.message;
    } finally {
      busy = false;
      properties.inert = false;
      inlineStorage.removeAttribute('aria-busy');
    }
  }

  inlineStorage.addEventListener('submit', event => {
    event.preventDefault();
    if (busy) return;
    if (stale) {
      status.textContent = 'This grid changed. Refresh before using storage actions.';
      return;
    }
    if (snapshot() !== saved) {
      status.textContent = 'Save your preparation changes first, then use storage actions.';
      return;
    }
    const form = event.target;
    const data = new FormData(form);
    if (form.method.toLowerCase() === 'post') {
      load(inlineStorage.dataset.url, {method: 'POST', body: data}, data.get('intent') === 'place');
    } else {
      const url = new URL(inlineStorage.dataset.url, window.location.href);
      for (const [key, value] of data) url.searchParams.set(key, value);
      load(url);
    }
  });
  inlineStorage.addEventListener('change', event => {
    const input = event.target;
    if (input.name === 'clipped') input.form.requestSubmit();
    if (input.id === 'box-search') {
      const options = panel.querySelector('#available-boxes').options;
      if ([...options].some(option => option.value === input.value)) input.form.requestSubmit();
    }
  });
  load(inlineStorage.dataset.url);
}
