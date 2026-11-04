// A small, dependency-free combobox for both inputs and multiline textareas.
// Selecting a suggestion changes only this field; typing new values remains valid.
const suggestionData = document.getElementById("preparation-suggestions");
if (suggestionData) {
  const suggestions = JSON.parse(suggestionData.textContent);
  document.querySelectorAll(".preparation-field").forEach((container) => {
    const input = container.querySelector("input, textarea");
    const values = input && suggestions[input.name];
    if (!input || !values || values.length === 0) return;
    let matches = [];
    let activeIndex = -1;
    let showingAll = false;
    const menu = document.createElement("ul");
    menu.id = `${input.id}-suggestions`;
    menu.className = "suggestion-menu";
    menu.setAttribute("role", "listbox");
    menu.hidden = true;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "suggestion-toggle";
    button.textContent = "Previous values ▾";
    button.setAttribute("aria-label", `Show previous values for ${input.labels[0]?.textContent || input.name}`);
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", menu.id);
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("autocomplete", "off");
    container.append(button, menu);

    function close() {
      menu.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      activeIndex = -1;
    }
    function choose(value) {
      input.value = value;
      input.dispatchEvent(new Event("input", {bubbles: true}));
      input.dispatchEvent(new Event("change", {bubbles: true}));
      close();
      input.focus();
    }
    function show() {
      const query = showingAll ? "" : input.value.toLocaleLowerCase();
      matches = values.filter((value) => value.toLocaleLowerCase().includes(query)).slice(0, 50);
      menu.replaceChildren();
      activeIndex = -1;
      input.removeAttribute("aria-activedescendant");
      matches.forEach((value, index) => {
        const option = document.createElement("li");
        option.id = `${menu.id}-${index}`;
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        option.textContent = value; // Private text is never interpreted as HTML.
        option.addEventListener("mousedown", (event) => event.preventDefault());
        option.addEventListener("click", () => choose(value));
        menu.append(option);
      });
      menu.hidden = matches.length === 0;
      input.setAttribute("aria-expanded", String(!menu.hidden));
    }
    input.addEventListener("input", () => { showingAll = false; show(); });
    input.addEventListener("focus", () => { showingAll = false; show(); });
    button.addEventListener("click", () => { input.focus(); showingAll = true; show(); });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { close(); return; }
      if (event.key === "Tab") { close(); return; }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (menu.hidden) show();
        if (matches.length === 0) return;
        event.preventDefault();
        if (activeIndex < 0) activeIndex = event.key === "ArrowDown" ? 0 : matches.length - 1;
        else activeIndex = (activeIndex + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length;
        [...menu.children].forEach((option, index) => option.setAttribute("aria-selected", String(index === activeIndex)));
        const active = menu.children[activeIndex];
        input.setAttribute("aria-activedescendant", active.id);
        active.scrollIntoView({block: "nearest"});
      } else if (event.key === "Enter" && !menu.hidden && activeIndex >= 0) {
        event.preventDefault();
        choose(matches[activeIndex]);
      }
    });
    document.addEventListener("click", (event) => { if (!container.contains(event.target)) close(); });
  });
}
