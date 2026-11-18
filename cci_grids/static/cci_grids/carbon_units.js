// Keep a conflicting existing value visible so it can be cleared deliberately.
const carbon = document.getElementById("id_carbon_description");
const nm = document.getElementById("id_carbon_thickness_nm");
const layers = document.getElementById("id_carbon_thickness_layers");
if (carbon && nm && layers) {
  function updateCarbonUnits() {
    const showNm = carbon.value === "amorphous carbon" || nm.value !== "";
    const showLayers = ["graphene", "graphene oxide"].includes(carbon.value) || layers.value !== "";
    nm.closest(".preparation-field").hidden = !showNm;
    layers.closest(".preparation-field").hidden = !showLayers;
  }
  carbon.addEventListener("change", updateCarbonUnits);
  nm.addEventListener("input", updateCarbonUnits);
  layers.addEventListener("input", updateCarbonUnits);
  updateCarbonUnits();
}
