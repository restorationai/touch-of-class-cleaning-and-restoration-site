export const openChatWidget = () => {
  const widgetBtn = document.getElementById('rai-toggle-btn');
  if (widgetBtn) {
    widgetBtn.click();
  } else {
    console.warn("Restoration AI chat widget not found on page.");
  }
};
