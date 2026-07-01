// Cassandra Content Script
// Listens to page loads/navigations, coordinates extraction and rendering flows.

let panel = null;

function initCassandra() {
  const isFilesTab = window.location.pathname.match(/\/pull\/\d+\/(files|changes)/);
  
  if (!isFilesTab) {
    // If we are not on the files changed tab, remove the panel if it exists
    const root = document.getElementById("cassandra-summary-panel-root");
    if (root) {
      root.remove();
    }
    panel = null;
    return;
  }
  
  // Initialize the panel if not already present
  if (!panel || !document.getElementById("cassandra-summary-panel-root")) {
    panel = new window.CassandraSummaryPanel();
  }
  
  // Show the initial CTA screen
  panel.showInitial(() => {
    panel.showLoading();
    
    let payload;
    try {
      payload = window.extractDiffFromDOM();
    } catch (e) {
      console.error("DOM Extraction failed:", e);
      panel.showError(`Failed to extract diff from DOM: ${e.message}`);
      return;
    }
    
    // Validate payload
    if (!payload || !payload.diff || payload.diff.length === 0) {
      panel.showError("No diff files extracted. Ensure you are in the Unified view and files are loaded.");
      return;
    }
    
    // Relay payload to background worker to fetch from Delphi endpoint
    chrome.runtime.sendMessage(
      {
        action: "fetch_review",
        payload: payload
      },
      (response) => {
        if (chrome.runtime.lastError) {
          panel.showError(`Relay communication failed: ${chrome.runtime.lastError.message}`);
          return;
        }
        
        if (response && response.success) {
          try {
            window.renderInlineComments(response.data.comments);
            panel.showSummary(response.data.summary, response.data.comments);
          } catch (renderError) {
            panel.showError(`Failed to render comments: ${renderError.message}`);
          }
        } else {
          const errorMsg = (response && response.error) ? response.error : "Unknown connection error to Delphi backend.";
          panel.showError(errorMsg);
        }
      }
    );
  });
}

// 1. Initial Page Load Listeners
if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", initCassandra);
} else {
  initCassandra();
}

// 2. GitHub SPA Navigation Event Listeners
document.addEventListener("turbo:load", initCassandra);
document.addEventListener("pjax:end", initCassandra);

// 3. Fallback URL polling using MutationObserver to capture GitHub client-side routing changes
let lastUrl = location.href;
const observer = new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    // Delay slightly to let the new DOM elements mount
    setTimeout(initCassandra, 600);
  }
});
observer.observe(document, { subtree: true, childList: true });
