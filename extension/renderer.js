// Cassandra UI Renderer (Universal Version)
// Renders comments inline in diffs and manages the floating glassmorphism summary panel.
// Robustly resolves target rows in both classic and React-based table grid components.

const CASSANDRA_SVG_ICON = `
  <svg class="cassandra-icon" viewBox="0 0 128 128" width="15" height="15" style="display:inline-block; vertical-align: middle;">
    <!-- White Slash -->
    <path d="M35 94 L62 34" stroke="#ffffff" stroke-width="12" stroke-linecap="round"/>
    <!-- White Capital C -->
    <text x="58" y="82" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="62" font-weight="900" fill="#ffffff">C</text>
    <!-- Purple Dot -->
    <circle cx="106" cy="86" r="9" fill="#8a2be2"/>
  </svg>
`;

function isDarkMode() {
  const mode = document.documentElement.getAttribute("data-color-mode");
  if (mode === "dark") return true;
  if (mode === "auto") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  return document.documentElement.getAttribute("data-dark-theme") !== null ||
         document.documentElement.classList.contains("dark") ||
         document.body.classList.contains("dark");
}

function parseMarkdown(text) {
  if (!text) return "";
  
  // Format bold (**bold**) and inline code (`code`)
  let html = text
    .replace(/\*\Delta(.*?)\*\?/g, "<strong>$1</strong>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.*?)`/g, "<code style='background: rgba(128,128,128,0.18); padding: 1.5px 4px; border-radius: 4px; font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, monospace; font-size: 0.88em; color: #ff7b72;'>$1</code>");
    
  // If in light mode, adjust code tag color to look readable
  if (!isDarkMode()) {
    html = html.replace(/color:\s*#ff7b72;/g, "color: #cf222e;");
  }

  const lines = html.split("\n");
  let resultHtml = "";
  let listStack = []; // Stack to keep track of nested list types ('ul', 'ol')
  
  for (const rawLine of lines) {
    const leadingSpaces = rawLine.match(/^\s*/)[0].length;
    const isIndented = leadingSpaces >= 2;
    const line = rawLine.trim();
    
    if (!line) continue;
    
    const isBullet = line.startsWith("* ") || line.startsWith("- ");
    const isNumbered = /^\d+\.\s+/.test(line);
    
    let content = line;
    if (isBullet) {
      content = line.substring(2);
    } else if (isNumbered) {
      content = line.replace(/^\d+\.\s+/, "");
    }
    
    let targetType = null;
    if (isBullet) targetType = "ul";
    else if (isNumbered) targetType = "ol";
    
    let targetDepth = 0;
    if (targetType) {
      targetDepth = isIndented ? 1 : 0;
    }
    
    if (targetType) {
      // 1. Close deeper lists
      while (listStack.length > targetDepth) {
        const type = listStack.pop();
        resultHtml += `</${type}>`;
      }
      
      // 2. Close mismatched list type at the same depth
      if (listStack.length === targetDepth + 1 && listStack[targetDepth] !== targetType) {
        const type = listStack.pop();
        resultHtml += `</${type}>`;
      }
      
      // 3. Open new list if needed
      if (listStack.length === targetDepth) {
        const listStyle = targetDepth === 1 
          ? "margin: 2px 0 8px 0; padding-left: 20px; font-size: 0.95em;" 
          : "margin: 8px 0; padding-left: 18px; list-style-type: square;";
        resultHtml += `<${targetType} style='${listStyle}'>`;
        listStack.push(targetType);
      }
      
      // 4. Append item list with responsive styling
      const itemStyle = targetDepth === 0 
        ? "margin-top: 10px; margin-bottom: 4px; font-weight: 600; font-size: 13.5px;" 
        : "margin-bottom: 5px; font-weight: 400; line-height: 1.45;";
      resultHtml += `<li style='${itemStyle}'>${content}</li>`;
    } else {
      // Close all lists if standard paragraph
      while (listStack.length > 0) {
        const type = listStack.pop();
        resultHtml += `</${type}>`;
      }
      resultHtml += `<p style='margin: 8px 0; line-height: 1.5;'>${line}</p>`;
    }
  }
  
  // Close any open tags
  while (listStack.length > 0) {
    const type = listStack.pop();
    resultHtml += `</${type}>`;
  }
  
  return resultHtml;
}

class CassandraSummaryPanel {
  constructor() {
    const existing = document.getElementById("cassandra-summary-panel-root");
    if (existing) {
      existing.remove();
    }
    
    this.container = document.createElement("div");
    this.container.id = "cassandra-summary-panel-root";
    this.container.style.position = "fixed";
    this.container.style.bottom = "24px";
    this.container.style.right = "24px";
    this.container.style.zIndex = "999999";
    document.body.appendChild(this.container);
    
    this.shadow = this.container.attachShadow({ mode: "open" });
    
    this.shadow.innerHTML = `
      <style>
        :host {
          --bg-color-light: rgba(255, 255, 255, 0.85);
          --bg-color-dark: rgba(13, 17, 23, 0.85);
          --border-light: rgba(210, 216, 222, 0.7);
          --border-dark: rgba(48, 54, 61, 0.8);
          --text-light: #24292f;
          --text-dark: #c9d1d9;
          --accent-light: #8a2be2;
          --accent-dark: #a372ff;
          
          --bg-color: var(--bg-color-light);
          --border-color: var(--border-light);
          --text-color: var(--text-light);
          --accent: var(--accent-light);
        }
        
        :host(.dark-theme) {
          --bg-color: var(--bg-color-dark);
          --border-color: var(--border-dark);
          --text-color: var(--text-dark);
          --accent: var(--accent-dark);
        }
        
        .panel {
          width: 360px;
          background: var(--bg-color);
          border: 1px solid var(--border-color);
          border-radius: 12px;
          padding: 16px;
          box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          color: var(--text-color);
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          font-size: 13px;
          line-height: 1.5;
          transition: all 0.2s ease-in-out;
        }
        
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid var(--border-color);
          padding-bottom: 8px;
          margin-bottom: 12px;
        }
        
        .title {
          font-weight: 600;
          font-size: 14px;
          display: flex;
          align-items: center;
        }
        
        .title-icon {
          margin-right: 6px;
          display: flex;
          align-items: center;
        }
        
        .close-btn {
          cursor: pointer;
          background: none;
          border: none;
          color: var(--text-color);
          opacity: 0.6;
          font-size: 18px;
          padding: 0 4px;
          line-height: 1;
        }
        
        .close-btn:hover {
          opacity: 1;
        }
        
        .content {
          max-height: 380px;
          overflow-y: auto;
          scrollbar-width: thin;
        }
        
        .loader {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 24px 0;
          text-align: center;
        }
        
        .spinner {
          width: 28px;
          height: 28px;
          border: 3px solid var(--border-color);
          border-top-color: var(--accent);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          margin-bottom: 12px;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        .error {
          color: #cf222e;
          font-weight: 500;
        }
        
        :host(.dark-theme) .error {
          color: #f85149;
        }
        
        .summary-text {
          font-size: 12.5px;
        }
        
        .run-review-btn {
          display: block;
          width: 100%;
          padding: 8px 12px;
          background-color: var(--accent);
          color: white;
          border: none;
          border-radius: 6px;
          font-weight: 600;
          font-size: 13px;
          cursor: pointer;
          text-align: center;
          margin-top: 10px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .run-review-btn:hover {
          opacity: 0.95;
        }
        
        /* Style accordions and hide default browser triangles */
        summary::-webkit-details-marker {
          display: none;
        }
        summary {
          list-style: none;
          outline: none;
          cursor: pointer;
        }
        details {
          margin-top: 8px;
          border: 1px solid var(--border-color);
          border-radius: 8px;
          padding: 8px 12px;
          background: rgba(128, 128, 128, 0.03);
          transition: background 0.25s ease;
        }
        details[open] {
          background: rgba(128, 128, 128, 0.06);
        }
      </style>
      <div class="panel" id="panel-body">
        <div class="header">
          <div class="title">
            <span class="title-icon">${CASSANDRA_SVG_ICON}</span>
            <span style="margin-left: 6px;">Cassandra Reviewer</span>
          </div>
          <button class="close-btn" id="close-panel">&times;</button>
        </div>
        <div class="content" id="panel-content">
          <!-- Dynamically populated -->
        </div>
      </div>
    `;
    
    this.shadow.getElementById("close-panel").addEventListener("click", () => {
      this.container.style.display = "none";
    });
  }
  
  updateTheme() {
    if (isDarkMode()) {
      this.shadow.host.classList.add("dark-theme");
    } else {
      this.shadow.host.classList.remove("dark-theme");
    }
  }
  
  showLoading() {
    this.updateTheme();
    this.container.style.display = "block";
    const content = this.shadow.getElementById("panel-content");
    content.innerHTML = `
      <div class="loader">
        <div class="spinner"></div>
        <div>Reviewing diffs with Cassandra repo indexing...</div>
      </div>
    `;
  }
  
  showError(errorMsg) {
    this.updateTheme();
    this.container.style.display = "block";
    const content = this.shadow.getElementById("panel-content");
    content.innerHTML = `
      <div class="error">
        <strong>Review failed:</strong>
        <p>${errorMsg}</p>
      </div>
    `;
  }
  
  showSummary(summaryData, comments) {
    this.updateTheme();
    this.container.style.display = "block";
    const content = this.shadow.getElementById("panel-content");
    
    const dark = isDarkMode();
    
    // 1. Calculate comments metrics (Chess.com evaluation report style)
    let errorCount = 0;
    let warningCount = 0;
    let infoCount = 0;
    
    if (comments && Array.isArray(comments)) {
      comments.forEach(c => {
        const sev = (c.severity || "").toLowerCase();
        if (sev === "error") errorCount++;
        else if (sev === "warning") warningCount++;
        else if (sev === "info") infoCount++;
      });
    }
    
    // Stats bar HTML
    const statsBarHtml = `
      <div style="display: flex; gap: 6px; margin-bottom: 12px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">
        <div style="flex: 1; display: flex; align-items: center; justify-content: center; background: rgba(248, 81, 73, 0.08); border: 1px solid rgba(248, 81, 73, 0.2); padding: 5px; border-radius: 6px; font-weight: 600; color: #f85149; font-size: 11px;">
          <span style="margin-right: 4px;">❌</span>
          <span>Errors: ${errorCount}</span>
        </div>
        <div style="flex: 1; display: flex; align-items: center; justify-content: center; background: rgba(210, 153, 34, 0.08); border: 1px solid rgba(210, 153, 34, 0.2); padding: 5px; border-radius: 6px; font-weight: 600; color: #d29922; font-size: 11px;">
          <span style="margin-right: 4px;">⚠️</span>
          <span>Warnings: ${warningCount}</span>
        </div>
        <div style="flex: 1; display: flex; align-items: center; justify-content: center; background: rgba(56, 139, 253, 0.08); border: 1px solid rgba(56, 139, 253, 0.2); padding: 5px; border-radius: 6px; font-weight: 600; color: #58a6ff; font-size: 11px;">
          <span style="margin-right: 4px;">ℹ️</span>
          <span>Infos: ${infoCount}</span>
        </div>
      </div>
    `;
    
    let html = statsBarHtml;
    
    // Emojis for each category
    const categoryIcons = {
      "Core Changes": "📂",
      "Architectural Impact": "🏗️",
      "Testing & Verification": "🧪"
    };
    
    if (typeof summaryData === "object" && summaryData !== null) {
      // Traverse categories
      for (const [category, items] of Object.entries(summaryData)) {
        const icon = categoryIcons[category] || "📝";
        
        let detailsContent = "";
        if (Array.isArray(items)) {
          detailsContent += "<ol style='margin: 0; padding-left: 20px; font-size: 0.95em;'>";
          for (const item of items) {
            let formattedItem = item
              .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
              .replace(/`(.*?)`/g, `<code style='background: rgba(128,128,128,0.18); padding: 1.5px 4px; border-radius: 4px; font-family: monospace; font-size: 0.88em; color: ${dark ? "#ff7b72" : "#cf222e"};'>$1</code>`);
            detailsContent += `<li style='margin-bottom: 6px; font-weight: 400; line-height: 1.45;'>${formattedItem}</li>`;
          }
          detailsContent += "</ol>";
        } else if (typeof items === "string") {
          let formattedItem = items
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/`(.*?)`/g, `<code style='background: rgba(128,128,128,0.18); padding: 1.5px 4px; border-radius: 4px; font-family: monospace; font-size: 0.88em; color: ${dark ? "#ff7b72" : "#cf222e"};'>$1</code>`);
          detailsContent += `<p style='margin: 0; font-weight: 400; line-height: 1.45;'>${formattedItem}</p>`;
        }
        
        // Wrap category inside collapsible detail/summary component (collapsed by default)
        html += `
          <details>
            <summary style="display: flex; align-items: center; justify-content: space-between; font-weight: 600; font-size: 13px; color: var(--accent); padding: 2px 0;">
              <span>${icon} ${category}</span>
              <span style="font-size: 10px; opacity: 0.6;">▼</span>
            </summary>
            <div style="margin-top: 8px; border-top: 1px solid var(--border-color); padding-top: 8px;">
              ${detailsContent}
            </div>
          </details>
        `;
      }
    } else {
      // Fallback: it is a markdown string
      html += parseMarkdown(summaryData);
    }
    
    content.innerHTML = `<div class="summary-text">${html}</div>`;
  }

  showInitial(onTriggerReview) {
    this.updateTheme();
    this.container.style.display = "block";
    const content = this.shadow.getElementById("panel-content");
    content.innerHTML = `
      <div>Ready to run context-aware PR review using Cassandra's local code index.</div>
      <button class="run-review-btn" id="run-review-btn">Run Cassandra Review</button>
    `;
    
    this.shadow.getElementById("run-review-btn").addEventListener("click", () => {
      onTriggerReview();
    });
  }
}

function renderInlineComments(comments) {
  document.querySelectorAll(".cassandra-inline-comment-container").forEach(el => el.remove());
  document.querySelectorAll(".cassandra-comment-row").forEach(el => el.remove());
  
  if (!comments || !comments.length) return;
  
  function extractPath(container) {
    let filePath = container.getAttribute("data-file-path");
    if (filePath) return filePath.trim();
    
    const header = container.querySelector(".file-header, [class*='file-header'], [class*='diff-file-header'], [class*='diffHeaderWrapper'], .js-file-header");
    if (header) {
      const titleLink = header.querySelector("a[title]");
      if (titleLink) return titleLink.getAttribute("title").trim();
      
      const primaryLink = header.querySelector("a.Link--primary, h3 a, h4 a");
      if (primaryLink) return primaryLink.textContent.trim();
      
      const clipboardEl = header.querySelector("[data-clipboard-text]");
      if (clipboardEl) return clipboardEl.getAttribute("data-clipboard-text").trim();
      
      const anyLink = header.querySelector("a, code");
      if (anyLink) return anyLink.textContent.trim();
    }
    return "";
  }
  
  const headers = document.querySelectorAll(".file-header, [class*='file-header'], [class*='diff-file-header'], [class*='diffHeaderWrapper'], .js-file-header");
  const fileBlocks = [];
  
  headers.forEach(header => {
    const filePath = extractPath(header);
    if (!filePath) return;
    
    let container = header;
    while (container && container.parentElement && container.parentElement !== document.body) {
      if (container.parentElement.querySelector(".blob-code-inner, .blob-code, [class*='blob-code'], [class*='code']")) {
        container = container.parentElement;
        break;
      }
      container = container.parentElement;
    }
    if (container) {
      fileBlocks.push({ file: filePath, container: container });
    }
  });

  const dark = isDarkMode();
  
  console.log("[Cassandra Diagnostic] File blocks resolved on page:", fileBlocks.map(b => b.file));
  console.log("[Cassandra Diagnostic] Comments to render:", comments.map(c => `${c.file}:${c.line} (${c.severity})`));

  comments.forEach(comment => {
    const cleanCommentFile = comment.file.replace(/\\/g, "/").toLowerCase();
    
    const block = fileBlocks.find(b => {
      const cleanBlockFile = b.file.replace(/\\/g, "/").toLowerCase();
      return cleanCommentFile.endsWith(cleanBlockFile) || 
             cleanBlockFile.endsWith(cleanCommentFile) ||
             cleanCommentFile.includes(cleanBlockFile) ||
             cleanBlockFile.includes(cleanCommentFile);
    });
    
    if (!block) {
      console.warn(`[Cassandra] Could not find file container matching: ${comment.file}`);
      return;
    }
    
    const targetContainer = block.container;
    const rows = targetContainer.querySelectorAll("tr, [class*='line-row'], [class*='diff-line-row']");
    let targetRow = null;
    
    for (const row of rows) {
      const numCells = Array.from(row.querySelectorAll("td, th, [role='gridcell']")).filter(cell => {
        const cls = (cell.className || "").toLowerCase();
        return cell.hasAttribute("data-line-number") || 
               cls.includes("line-number") || 
               cls.includes("num") || 
               /^\d+$/.test(cell.textContent.trim());
      });
      
      if (numCells.length >= 2) {
        const newLineCell = numCells[1];
        const lineAttr = newLineCell.getAttribute("data-line-number") || newLineCell.getAttribute("data-line");
        const lineText = newLineCell.textContent.trim();
        
        if (lineAttr === String(comment.line) || lineText === String(comment.line)) {
          const cellClass = newLineCell.className.toLowerCase();
          if (lineText !== "" && !cellClass.includes("delete") && !cellClass.includes("removal") && !cellClass.includes("deleted")) {
            targetRow = row;
            break;
          }
        }
      } else if (numCells.length === 1) {
        const cell = numCells[0];
        const lineAttr = cell.getAttribute("data-line-number") || cell.getAttribute("data-line");
        const lineText = cell.textContent.trim();
        
        if (lineAttr === String(comment.line) || lineText === String(comment.line)) {
          targetRow = row;
          break;
        }
      }
    }
    
    if (!targetRow) {
      console.warn(`[Cassandra] Could not find row matching line: ${comment.line} in file ${comment.file}`);
      return;
    }
    
    const codeCell = targetRow.querySelector("td.diff-text-cell, td.blob-code, [class*='code-cell'], [class*='blob-code']");
    if (!codeCell) {
      console.warn(`[Cassandra] Could not find code cell inside target row for line: ${comment.line}`);
      return;
    }
    
    const commentDiv = document.createElement("div");
    commentDiv.className = "cassandra-inline-comment-container";
    commentDiv.style.display = "block";
    commentDiv.style.marginTop = "8px";
    commentDiv.style.marginBottom = "8px";
    commentDiv.style.width = "100%";
    commentDiv.style.clear = "both";
    
    const severityClass = `cassandra-badge-${comment.severity.toLowerCase()}`;
    const severityText = comment.severity.toUpperCase();
    
    commentDiv.innerHTML = `
      <div class="cassandra-inline-comment pr-reviewer-comment${dark ? " cassandra-dark" : ""}" style="margin: 6px 0; max-width: 96%; text-align: left;">
        <div class="cassandra-comment-header">
          ${CASSANDRA_SVG_ICON}
          <span class="cassandra-comment-author" style="margin-left: 6px; font-weight: 600;">Cassandra Review</span>
          <span class="cassandra-comment-badge ${severityClass}" style="margin-left: 8px;">${severityText}</span>
        </div>
        <div class="cassandra-comment-body" style="margin-top: 6px; font-weight: 400; font-size: 12.5px; line-height: 1.45; white-space: pre-wrap;">${comment.text}</div>
      </div>
    `;
    
    codeCell.appendChild(commentDiv);
    console.log(`[Cassandra] Successfully rendered cell-inline comment on line ${comment.line} of ${comment.file}`);
  });
}

// Export to window object
window.CassandraSummaryPanel = CassandraSummaryPanel;
window.renderInlineComments = renderInlineComments;
