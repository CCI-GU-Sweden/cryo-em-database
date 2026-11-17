document.querySelectorAll('[data-group-controls]').forEach(controls => {
  const root = controls.closest('[data-grid-properties]') || controls.closest('form');
  if (!root) return;
  const groups = root.querySelectorAll('[data-preparation-group]');
  controls.hidden = false;
  controls.querySelector('[data-expand-groups]').addEventListener('click', () => {
    groups.forEach(group => { group.open = true; });
  });
  controls.querySelector('[data-collapse-groups]').addEventListener('click', () => {
    groups.forEach(group => { group.open = false; });
  });
  // Reveal browser validation errors before the browser focuses their controls.
  document.addEventListener('invalid', event => {
    const group = event.target.closest('[data-preparation-group]');
    if (group) group.open = true;
  }, true);
});
