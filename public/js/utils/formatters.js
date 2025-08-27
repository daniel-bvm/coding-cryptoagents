// Utility functions for formatting
class Formatters {
  static formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
  }

  static formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  static formatTimeAgo(date) {
    const now = new Date();
    const diffInSeconds = Math.floor((now - new Date(date)) / 1000);

    if (diffInSeconds < 60) return `${diffInSeconds}s ago`;
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400)
      return `${Math.floor(diffInSeconds / 3600)}h ago`;

    return `${Math.floor(diffInSeconds / 86400)}d ago`;
  }

  static escapeHtmlInMarkdown(text) {
    return text.replace(/<(\w+)>/g, "`<$1>`");
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.Formatters = Formatters;
}
