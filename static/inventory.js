// Cierra los formularios flotantes al salir de ellos o elegir otra acción.
const actionPanels = document.querySelectorAll(".actions details");

document.addEventListener("click", (event) => {
  const currentPanel = event.target.closest(".actions details");
  actionPanels.forEach((panel) => {
    if (panel !== currentPanel) panel.open = false;
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;

  const focusedPanel = document.activeElement.closest(".actions details");
  actionPanels.forEach((panel) => { panel.open = false; });
  if (focusedPanel) focusedPanel.querySelector("summary").focus();
});
