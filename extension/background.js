// Cassandra MV3 background service worker
// Used as a relay to bypass GitHub page CSP (Content Security Policy) and CORS blocks
// when contacting the local Delphi backend.

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "fetch_review") {
    const backendUrl = request.backendUrl || "http://localhost:8000/review";
    
    fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(request.payload)
    })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Server returned ${response.status}: ${text || response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      sendResponse({ success: true, data: data });
    })
    .catch((error) => {
      console.error("Error fetching review:", error);
      sendResponse({ success: false, error: error.message });
    });
    
    return true; // Keep the message channel open for sendResponse
  }
});
