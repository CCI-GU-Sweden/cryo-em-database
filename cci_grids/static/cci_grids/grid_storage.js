const boxSelection = document.getElementById('box-selection');
if (boxSelection) {
  const input = document.getElementById('box-search');
  const clipped = boxSelection.querySelector('input[type="checkbox"][name="clipped"]');
  // Reload the eligible boxes and slot form together whenever clipping changes.
  clipped?.addEventListener('change', () => boxSelection.requestSubmit());
  input.addEventListener('change', () => {
    const options = document.getElementById('available-boxes').options;
    if ([...options].some(option => option.value === input.value)) {
      boxSelection.requestSubmit();
    }
  });
}
