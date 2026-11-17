// Browsers implicitly submit forms when Enter is pressed in a single-line field.
// For batch creation, require an explicit action on the Create grids button.
const sessionForm = document.getElementById("new-session-form");
if (sessionForm) {
  sessionForm.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.defaultPrevented || event.isComposing) return;
    const field = event.target;
    if (field.tagName === "SELECT" ||
        (field.tagName === "INPUT" && !["submit", "button", "reset"].includes(field.type))) {
      event.preventDefault();
    }
    // Textareas keep newlines. Buttons keep normal keyboard activation.
    // Suggestion menus handle their own Enter key before it reaches this form.
  });
}
