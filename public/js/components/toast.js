// Toast notification system
class ToastManager {
  constructor() {
    this.container = DomUtils.getContainer("toast-container");
    this.config = window.APP_CONFIG?.TOAST_CONFIG || {};
  }

  showToast(message, type = "info", duration = null) {
    const actualDuration = duration || this.config.duration?.[type] || 5000;
    const toast = this.createToast(message, type);
    this.animateIn(toast);

    setTimeout(() => {
      this.animateOut(toast);
    }, actualDuration);

    return toast.id;
  }

  showConnectionToast(message, type = "info") {
    // Remove existing connection toasts
    this.container
      .querySelectorAll(".connection-toast")
      .forEach((toast) => toast.remove());

    const toast = this.createConnectionToast(message, type);
    this.animateIn(toast);

    if (type === "success") {
      setTimeout(() => this.animateOut(toast), 3000);
    }

    return toast.id;
  }

  showAdvancedToast({
    title,
    message,
    type = "info",
    duration = 5000,
    icon = null,
    details = null,
  }) {
    const toast = this.createAdvancedToast({
      title,
      message,
      type,
      icon,
      details,
    });
    this.animateIn(toast);

    setTimeout(() => {
      this.animateOut(toast);
    }, duration);

    return toast.id;
  }

  createToast(message, type) {
    const toast = DomUtils.createElement("div");
    const toastId = `toast-${Date.now()}-${Math.random()
      .toString(36)
      .substr(2, 9)}`;

    const icons = this.config.icons || {
      success: "fas fa-check-circle text-green-500",
      error: "fas fa-exclamation-circle text-red-500",
      info: "fas fa-info-circle text-blue-500",
      warning: "fas fa-exclamation-triangle text-yellow-500",
    };

    const colors = {
      success: "bg-green-50 border-green-200 text-green-800",
      error: "bg-red-50 border-red-200 text-red-800",
      info: "bg-blue-50 border-blue-200 text-blue-800",
      warning: "bg-yellow-50 border-yellow-200 text-yellow-800",
    };

    toast.id = toastId;
    toast.className = `flex items-center p-4 mb-2 border rounded-lg shadow-lg transform transition-all duration-300 ease-in-out translate-x-full opacity-0 ${colors[type]}`;
    toast.innerHTML = `
            <i class="${icons[type]} mr-3"></i>
            <span class="flex-1">${message}</span>
            <button onclick="this.parentElement.remove()" class="ml-3 text-gray-400 hover:text-gray-600">
                <i class="fas fa-times"></i>
            </button>
        `;

    this.container.appendChild(toast);
    return toast;
  }

  createConnectionToast(message, type) {
    const toast = DomUtils.createElement("div");
    const toastId = `connection-toast-${Date.now()}`;

    const colors = {
      success: "bg-green-50 border-green-200 text-green-800",
      warning: "bg-yellow-50 border-yellow-200 text-yellow-800",
      info: "bg-blue-50 border-blue-200 text-blue-800",
      error: "bg-red-50 border-red-200 text-red-800",
    };

    const icons = {
      success: "fas fa-wifi text-green-500",
      warning: "fas fa-exclamation-triangle text-yellow-500",
      info: "fas fa-sync fa-spin text-blue-500",
      error: "fas fa-wifi-slash text-red-500",
    };

    toast.id = toastId;
    toast.className = `connection-toast flex items-center p-3 mb-2 border rounded-lg shadow-lg transform transition-all duration-300 ease-in-out translate-x-full opacity-0 ${colors[type]}`;
    toast.innerHTML = `
            <i class="${icons[type]} mr-2 text-sm"></i>
            <span class="flex-1 text-sm">${message}</span>
            ${
              type === "success"
                ? `<button onclick="this.parentElement.remove()" class="ml-2 text-gray-400 hover:text-gray-600">
                <i class="fas fa-times text-xs"></i>
            </button>`
                : ""
            }
        `;

    this.container.appendChild(toast);
    return toast;
  }

  createAdvancedToast({ title, message, type, icon, details }) {
    const toast = DomUtils.createElement("div");
    const toastId = `advanced-toast-${Date.now()}`;

    const colors = {
      success:
        "bg-gradient-to-r from-green-50 to-green-100 border-green-300 text-green-900",
      error:
        "bg-gradient-to-r from-red-50 to-red-100 border-red-300 text-red-900",
      info: "bg-gradient-to-r from-blue-50 to-blue-100 border-blue-300 text-blue-900",
      warning:
        "bg-gradient-to-r from-yellow-50 to-yellow-100 border-yellow-300 text-yellow-900",
    };

    const iconDisplay =
      icon ||
      (type === "success"
        ? "✅"
        : type === "error"
        ? "❌"
        : type === "warning"
        ? "⚠️"
        : "ℹ️");

    toast.id = toastId;
    toast.className = `relative p-4 mb-3 border-l-4 rounded-lg shadow-xl transform transition-all duration-500 ease-in-out translate-x-full opacity-0 max-w-md ${colors[type]}`;
    toast.innerHTML = `
            <div class="flex items-start">
                <div class="text-2xl mr-3 animate-bounce-gentle">${iconDisplay}</div>
                <div class="flex-1">
                    <div class="font-bold text-sm mb-1">${title}</div>
                    <div class="text-sm mb-2">${message}</div>
                    ${
                      details
                        ? `<div class="text-xs opacity-75">${details}</div>`
                        : ""
                    }
                </div>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-gray-400 hover:text-gray-600 transition-colors">
                    <i class="fas fa-times text-xs"></i>
                </button>
            </div>
        `;

    this.container.appendChild(toast);
    return toast;
  }

  animateIn(toast) {
    setTimeout(() => {
      toast.style.opacity = "1";
      toast.style.transform = "translateX(0)";
    }, 10);
  }

  animateOut(toast) {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.ToastManager = ToastManager;
}
