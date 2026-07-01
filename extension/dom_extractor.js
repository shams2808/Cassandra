// Cassandra DOM Extractor (Universal Bottom-Up Scraper)
// Scrapes the code cells bottom-up, maps them to their respective file headers,
// and resolves diff markers (+/-) using CSS classes and native attributes.
// Compatible with both classic and modern React-based GitHub PR layouts.

function extractDiffFromDOM() {
  const pathParts = window.location.pathname.split('/');
  const repo_id = (pathParts[1] && pathParts[2]) ? `${pathParts[1]}/${pathParts[2]}` : "";
  
  const titleEl = document.querySelector(".js-issue-title") || 
                  document.querySelector(".pr-header-directory .title") || 
                  document.querySelector("h1.gh-header-title");
  const pr_title = titleEl ? titleEl.textContent.trim() : "";
  
  const descEl = document.querySelector(".js-comment-body");
  const pr_description = descEl ? descEl.textContent.trim() : "";
  
  const diffMap = new Map(); // file_path -> { status: string, lines: array }
  
  // Helper to extract file path from a file block header
  function extractPath(header) {
    let filePath = header.getAttribute("data-file-path") || header.closest("[data-file-path]")?.getAttribute("data-file-path");
    if (filePath) return filePath.trim();
    
    // Check title attribute of link inside header (common tooltip)
    const titleLink = header.querySelector("a[title]");
    if (titleLink) {
      const t = titleLink.getAttribute("title");
      if (t) return t.trim();
    }
    
    // Check Link--primary or h3/h4 links
    const primaryLink = header.querySelector("a.Link--primary, h3 a, h4 a");
    if (primaryLink) {
      const txt = primaryLink.textContent.trim();
      if (txt) return txt;
    }
    
    // Check data-clipboard-text (from copy buttons)
    const clipboardEl = header.querySelector("[data-clipboard-text]");
    if (clipboardEl) {
      const clip = clipboardEl.getAttribute("data-clipboard-text");
      if (clip) return clip.trim();
    }
    
    // Fallback: check any link or code tag
    const anyLink = header.querySelector("a, code");
    if (anyLink) {
      const txt = anyLink.textContent.trim();
      if (txt) return txt;
    }
    
    return "";
  }

  // 1. Scan all code cells bottom-up
  // Matches classic (.blob-code-inner) and modern React (.diff-text-inner, code.diff-text, td.diff-text-cell)
  const codeCells = document.querySelectorAll(".diff-text-inner, .blob-code-inner, code.diff-text, td.diff-text-cell, .blob-code");
  console.log(`[Cassandra] Found ${codeCells.length} code cells globally.`);
  
  codeCells.forEach((codeCell) => {
    // Traverse upwards to find the first ancestor that contains a file header
    let container = codeCell.parentElement;
    let header = null;
    while (container && container.parentElement && container.parentElement !== document.body) {
      header = container.querySelector(".file-header, [class*='file-header'], [class*='diff-file-header'], [class*='diffHeaderWrapper'], .js-file-header");
      if (header) {
        break;
      }
      container = container.parentElement;
    }
    
    if (!container || !header) return;
    
    const filePath = extractPath(header);
    if (!filePath) return;
    
    if (!diffMap.has(filePath)) {
      // Determine status
      let status = "modified";
      const headerText = header.textContent.toLowerCase();
      const isDeleted = container.querySelector('.diffstat-status-deleted') !== null || headerText.includes("deleted");
      const isAdded = container.querySelector('.diffstat-status-added') !== null || headerText.includes("added");
      const isRenamed = container.querySelector('.diffstat-status-renamed') !== null || headerText.includes("→") || headerText.includes("renamed");
      
      if (isDeleted) status = "removed";
      else if (isAdded) status = "added";
      else if (isRenamed) status = "renamed";
      
      diffMap.set(filePath, {
        status: status,
        lines: []
      });
    }
    
    const fileDiff = diffMap.get(filePath);
    
    // Skip if this is a hunk header marker
    if (codeCell.classList.contains("blob-code-hunk") || codeCell.closest(".blob-code-hunk")) {
      fileDiff.lines.push(codeCell.textContent.trim());
      return;
    }
    
    // Resolve prefix marker (+ for addition, - for deletion, space for context)
    let marker = "";
    const codeRow = codeCell.closest("tr, [class*='row'], [class*='line']");
    const codeContainer = codeCell.closest("code, td, div");
    
    // Gather all classes on cell/container/row to check for addition/deletion classes
    const classStr = (
      codeCell.className + " " + 
      (codeContainer ? codeContainer.className : "") + " " + 
      (codeRow ? codeRow.className : "")
    ).toLowerCase();
    
    if (classStr.includes("addition") || classStr.includes("added") || classStr.includes("add")) {
      marker = "+";
    } else if (classStr.includes("deletion") || classStr.includes("removed") || classStr.includes("deleted") || classStr.includes("removal") || classStr.includes("del")) {
      marker = "-";
    } else {
      // Fallback to data-code-marker attribute
      marker = codeCell.getAttribute("data-code-marker") || codeContainer?.getAttribute("data-code-marker") || " ";
    }
    
    const codeText = codeCell.textContent || "";
    fileDiff.lines.push(marker + codeText);
  });
  
  // 2. Scan collapsed files (load buttons) that haven't loaded cells yet
  const loadButtons = document.querySelectorAll('.js-diff-load-button, button.load-diff-button, .load-diff-container button');
  loadButtons.forEach((button) => {
    let container = button.parentElement;
    let header = null;
    while (container && container.parentElement && container.parentElement !== document.body) {
      header = container.querySelector(".file-header, [class*='file-header'], [class*='diff-file-header'], [class*='diffHeaderWrapper'], .js-file-header");
      if (header) {
        break;
      }
      container = container.parentElement;
    }
    
    if (!container || !header) return;
    
    const filePath = extractPath(header);
    if (!filePath) return;
    
    // Auto-trigger expand
    button.click();
    
    if (!diffMap.has(filePath)) {
      diffMap.set(filePath, {
        status: "modified",
        lines: ["COLLAPSED_UNAVAILABLE: File was collapsed. Expanding file now... Please try reviewing again."]
      });
    }
  });
  
  // Format response diff list
  const diffs = [];
  diffMap.forEach((val, key) => {
    diffs.push({
      file: key,
      patch: val.lines.join("\n"),
      status: val.status
    });
  });
  
  return {
    repo_id: repo_id,
    pr_title: pr_title,
    pr_description: pr_description,
    diff: diffs
  };
}

// Export to window
window.extractDiffFromDOM = extractDiffFromDOM;
window.runDiagnostic = function() { console.log("Diagnostic complete."); };
