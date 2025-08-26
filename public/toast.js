// Toast notification system
class ToastManager {
  constructor() {
    this.container = null;
    // Don't initialize immediately, wait for DOM to be ready
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => this.init());
    } else {
      this.init();
    }
  }

  init() {
    this.container = document.getElementById("toast-container");
    if (!this.container) {
      this.container = document.createElement("div");
      this.container.id = "toast-container";
      this.container.className = "fixed top-4 right-4 z-50 space-y-2";
      document.body.appendChild(this.container);
    }
  }

  show(message, type = "info", duration = CONSTANTS.TOAST_DURATION) {
    if (!this.container) {
      console.warn("ToastManager not initialized yet");
      return;
    }
    const toast = this.createToast(message, type);
    this.container.appendChild(toast);
    this.animateIn(toast);
    this.scheduleRemoval(toast, duration);
  }

  showConnection(message, type = "info") {
    if (!this.container) {
      console.warn("ToastManager not initialized yet");
      return;
    }
    // Remove existing connection toasts
    this.container
      .querySelectorAll(".connection-toast")
      .forEach((toast) => toast.remove());

    const toast = this.createConnectionToast(message, type);
    this.container.appendChild(toast);
    this.animateIn(toast);

    if (type === "success") {
      this.scheduleRemoval(toast, CONSTANTS.CONNECTION_TOAST_DURATION);
    }
  }

  showAdvanced({
    title,
    message,
    type = "info",
    duration = CONSTANTS.TOAST_DURATION,
    icon = null,
    details = null,
  }) {
    if (!this.container) {
      console.warn("ToastManager not initialized yet");
      return;
    }
    const toast = this.createAdvancedToast({
      title,
      message,
      type,
      icon,
      details,
      duration,
    });
    this.container.appendChild(toast);
    this.animateIn(toast);
    this.scheduleRemoval(toast, duration);
  }

  createToast(message, type) {
    const toast = document.createElement("div");
    const { icons, colors } = TOAST_CONFIGS;

    toast.className = `flex items-center p-4 mb-2 border rounded-lg shadow-lg transform transition-all duration-300 ease-in-out translate-x-full opacity-0 ${colors[type]}`;
    toast.innerHTML = `
      <i class="${icons[type]} mr-3"></i>
      <span class="flex-1">${message}</span>
      <button onclick="this.parentElement.remove()" class="ml-3 text-gray-400 hover:text-gray-600">
        <i class="fas fa-times"></i>
      </button>
    `;
    return toast;
  }

  createConnectionToast(message, type) {
    const toast = document.createElement("div");
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

    toast.className = `connection-toast flex items-center p-3 mb-2 border rounded-lg shadow-lg transform transition-all duration-300 ease-in-out translate-x-full opacity-0 ${colors[type]}`;
    toast.innerHTML = `
      <i class="${icons[type]} mr-2 text-sm"></i>
      <span class="flex-1 text-sm">${message}</span>
      ${
        type === "success"
          ? `
        <button onclick="this.parentElement.remove()" class="ml-2 text-gray-400 hover:text-gray-600">
          <i class="fas fa-times text-xs"></i>
        </button>
      `
          : ""
      }
    `;
    return toast;
  }

  createAdvancedToast({ title, message, type, icon, details, duration }) {
    const toast = document.createElement("div");
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

    toast.className = `relative p-4 mb-3 border-l-4 rounded-lg shadow-xl transform transition-all duration-500 ease-in-out translate-x-full opacity-0 max-w-md ${colors[type]}`;
    toast.innerHTML = `
      <div class="flex items-start">
        <div class="text-2xl mr-3 animate-bounce-gentle">${iconDisplay}</div>
        <div class="flex-1">
          <div class="font-bold text-sm mb-1">${title}</div>
          <div class="text-sm mb-2">${message}</div>
          ${details ? (details.startsWith('http') ? 
            `<div class="text-xs opacity-75">
              <input type="text" value="${details}" readonly 
                     class="w-full p-1 border rounded text-xs bg-white cursor-pointer" 
                     onclick="this.select()" 
                     title="Click to select URL" />
            </div>` : 
            `<div class="text-xs opacity-75">${details}</div>`) : ""}
        </div>
        <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-gray-400 hover:text-gray-600 transition-colors">
          <i class="fas fa-times text-xs"></i>
        </button>
      </div>
      <div class="absolute bottom-0 left-0 h-1 bg-current opacity-20 transition-all duration-${duration} ease-linear" style="width: 100%"></div>
    `;
    return toast;
  }

  animateIn(toast) {
    setTimeout(() => {
      toast.classList.remove("translate-x-full", "opacity-0");
      // Start progress bar animation for advanced toasts
      const progressBar = toast.querySelector(".absolute.bottom-0");
      if (progressBar) {
        setTimeout(() => {
          progressBar.style.width = "0%";
        }, 100);
      }
    }, 10);
  }

  scheduleRemoval(toast, duration) {
    setTimeout(() => {
      if (toast.parentElement) {
        toast.classList.add("translate-x-full", "opacity-0");
        setTimeout(() => {
          if (toast.parentElement) {
            toast.remove();
          }
        }, 300);
      }
    }, duration);
  }
}

// Create global toast manager instance
const toastManager = new ToastManager();
