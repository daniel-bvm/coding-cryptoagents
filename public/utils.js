// Utility functions and constants
const CONSTANTS = {
  CDN_BASE_URL: "https://cdn.eternalai.org/prototype-agent",
  RECONNECT_DELAY: 2000,
  MAX_PLAN_ACTIVITIES: 20,
  TOAST_DURATION: 5000,
  CONNECTION_TOAST_DURATION: 3000,
};

const STATUS_CONFIGS = {
  colors: {
    pending: "bg-gray-100 text-gray-800",
    processing: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  },
  textColors: {
    pending: "text-gray-600",
    processing: "text-blue-600",
    completed: "text-green-600",
    failed: "text-red-600",
  },
  progressColors: {
    pending: "bg-gray-400",
    processing: "bg-blue-500",
    completed: "bg-green-500",
    failed: "bg-red-500",
  },
};

const STEP_CONFIGS = {
  colors: {
    pending: "bg-gray-100 text-gray-600 border-gray-300",
    executing: "bg-blue-100 text-blue-700 border-blue-300",
    completed: "bg-green-100 text-green-700 border-green-300",
    failed: "bg-red-100 text-red-700 border-red-300",
  },
  icons: {
    pending: "fas fa-clock text-gray-500",
    executing: "fas fa-cog fa-spin text-blue-500",
    completed: "fas fa-check-circle text-green-500",
    failed: "fas fa-times-circle text-red-500",
  },
};

const TOAST_CONFIGS = {
  icons: {
    success: "fas fa-check-circle text-green-500",
    error: "fas fa-exclamation-circle text-red-500",
    info: "fas fa-info-circle text-blue-500",
    warning: "fas fa-exclamation-triangle text-yellow-500",
  },
  colors: {
    success: "bg-green-50 border-green-200 text-green-800",
    error: "bg-red-50 border-red-200 text-red-800",
    info: "bg-blue-50 border-blue-200 text-blue-800",
    warning: "bg-yellow-50 border-yellow-200 text-yellow-800",
  },
};

// Utility functions
const utils = {
  formatDate(dateString) {
    return new Date(dateString).toLocaleString();
  },

  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  },

  formatTimeAgo(date) {
    const now = new Date();
    const diffInSeconds = Math.floor((now - new Date(date)) / 1000);

    if (diffInSeconds < 60) return "just now";
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400)
      return `${Math.floor(diffInSeconds / 3600)}h ago`;
    return `${Math.floor(diffInSeconds / 86400)}d ago`;
  },

  escapeHtmlInMarkdown(text) {
    return text.replace(/<(\w+)>/g, "`<$1>`");
  },

  getStepTypeIcon(stepType) {
    return stepType === "research" ? "🔍" : "🔨";
  },

  findBestHtmlFile(taskFiles) {
    if (!Array.isArray(taskFiles) || taskFiles.length === 0) {
      return null;
    }

    // Prefer index.html first
    const indexFile = taskFiles.find((f) =>
      f.path.toLowerCase().endsWith("index.html")
    );
    if (indexFile) return indexFile.path;

    // Otherwise, use the first HTML file
    const firstHTML = taskFiles.find((f) =>
      f.path.toLowerCase().endsWith(".html")
    );
    return firstHTML ? firstHTML.path : null;
  },

  async copyToClipboard(text) {
    try {
      // Try modern clipboard API first
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
      
      // Fallback for browsers that don't support clipboard API or HTTP contexts
      return this.fallbackCopyToClipboard(text);
    } catch (err) {
      console.error("Failed to copy to clipboard:", err);
      // Try fallback method if modern API fails
      return this.fallbackCopyToClipboard(text);
    }
  },

  fallbackCopyToClipboard(text) {
    try {
      // Create a temporary textarea element
      const textArea = document.createElement("textarea");
      textArea.value = text;
      
      // Make it invisible but still accessible to the browser
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      textArea.style.top = "-999999px";
      
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      
      // Try to copy using the older execCommand method
      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);
      
      if (successful) {
        return true;
      } else {
        console.error("Fallback copy method failed");
        return false;
      }
    } catch (err) {
      console.error("Fallback copy method failed:", err);
      return false;
    }
  },
};
