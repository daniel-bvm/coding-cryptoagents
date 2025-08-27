// Configuration constants
const CDN_BASE_URL = "https://cdn.eternalai.org/prototype-agent";

const UPLOAD_CONFIG = {
  enforceMinimumStepTiming: true,
  minimumStepTimes: {
    preparation: 500,
    zipCreation: 600,
    analysis: 500,
    uploadPrep: 600,
    uploadStep: 400,
    processing: 500,
    extraction: 400,
  },
};

const TOAST_CONFIG = {
  duration: {
    default: 5000,
    success: 3000,
    error: 7000,
    connection: 3000,
  },
  icons: {
    success: "fas fa-check-circle text-green-500",
    error: "fas fa-exclamation-circle text-red-500",
    info: "fas fa-info-circle text-blue-500",
    warning: "fas fa-exclamation-triangle text-yellow-500",
  },
};

const STATUS_COLORS = {
  pending: "bg-gray-100 text-gray-800",
  processing: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const PROGRESS_COLORS = {
  pending: "bg-gray-400",
  processing: "bg-blue-500",
  completed: "bg-green-500",
  failed: "bg-red-500",
};

const STEP_STATUS_COLORS = {
  pending: "bg-gray-100 text-gray-600 border-gray-300",
  executing: "bg-blue-100 text-blue-700 border-blue-300",
  completed: "bg-green-100 text-green-700 border-green-300",
  failed: "bg-red-100 text-red-700 border-red-300",
};

const STEP_STATUS_ICONS = {
  pending: "fas fa-clock text-gray-500",
  executing: "fas fa-cog fa-spin text-blue-500",
  completed: "fas fa-check-circle text-green-500",
  failed: "fas fa-times-circle text-red-500",
};

// Export for use in other modules
if (typeof window !== "undefined") {
  window.APP_CONFIG = {
    CDN_BASE_URL,
    UPLOAD_CONFIG,
    TOAST_CONFIG,
    STATUS_COLORS,
    PROGRESS_COLORS,
    STEP_STATUS_COLORS,
    STEP_STATUS_ICONS,
  };
}
