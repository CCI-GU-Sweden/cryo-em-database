// Enhance the admin form without changing its normal save behavior. The server
// checks uniqueness for previews and allocates the authoritative code on save.
document.addEventListener("DOMContentLoaded", () => {
  const name = document.getElementById("id_name");
  const code = document.getElementById("id_owner_code_preview");
  if (!name || !code || name.dataset.codeCreating !== "true") return;

  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Create unique code";
  button.className = "owner-code-button";
  name.insertAdjacentElement("afterend", button);

  const status = document.createElement("p");
  status.className = "help";
  status.setAttribute("role", "status");
  code.insertAdjacentElement("afterend", status);

  name.addEventListener("input", () => {
    code.value = "";
    status.textContent = "Click Create unique code. Codes contain four lowercase letters/digits.";
  });

  button.addEventListener("click", async () => {
    const requestedName = name.value.trim();
    if (!requestedName) {
      status.textContent = "Enter the sample owner's name first.";
      name.focus();
      return;
    }
    button.disabled = true;
    status.textContent = "Checking existing owner codes…";
    try {
      const url = new URL(name.dataset.codeUrl, window.location.origin);
      url.searchParams.set("name", requestedName);
      const response = await fetch(url, {credentials: "same-origin"});
      const result = await response.json();
      // Do not display an old response if the name was edited while waiting.
      if (name.value.trim() !== requestedName) return;
      if (!response.ok) throw new Error(result.error || "Could not create a code.");
      code.value = result.code;
      status.textContent = "This code is currently unused. Save checks uniqueness again.";
    } catch (error) {
      status.textContent = "Could not create a code. Please try again.";
    } finally {
      button.disabled = false;
    }
  });
});
