// Main application entry point
function dashboard() {
  // Return a simple object that Alpine.js can use directly
  return {
    // Core state
    tasks: [],
    selectedTask: null,
    taskFiles: [],
    showHTMLFile: "",
    taskSteps: [],
    viewTaskSteps: true,
    loading: false,
    planActivity: [],

    // Manager instances
    api: null,
    toastManager: null,
    realtimeManager: null,
    folderTree: null,

    async init() {
      // Initialize managers
      this.api = new ApiClient();
      this.toastManager = new ToastManager();
      this.realtimeManager = new RealtimeManager(this);
      this.folderTree = new FolderTreeManager();
      this.modalManager = new ModalManager(this);
      this.uploadManager = new UploadManager(this);

      // Load initial data
      await this.refreshTasks();
      this.realtimeManager.connect();
      this.setupEventListeners();
    },

    setupEventListeners() {
      // Network status handling
      document.addEventListener("visibilitychange", () => {
        if (
          !document.hidden &&
          this.realtimeManager.connectionStatus === "disconnected"
        ) {
          this.realtimeManager.connect();
        }
      });

      window.addEventListener("online", () => {
        if (this.realtimeManager.connectionStatus === "disconnected") {
          this.realtimeManager.connect();
        }
      });

      window.addEventListener("offline", () => {
        this.realtimeManager.connectionStatus = "disconnected";
        this.toastManager.showConnectionToast("Network offline", "error");
      });
    },

    // Template methods that return HTML strings
    renderHeader() {
      return Templates.header(this);
    },

    renderStatsCards() {
      return Templates.statsCards();
    },

    renderTaskList() {
      return Templates.taskList();
    },

    renderModal() {
      return Templates.modal();
    },

    // Computed properties
    get completedTasks() {
      return this.tasks.filter((task) => task.status === "completed").length;
    },

    get inProgressTasks() {
      return this.tasks.filter((task) => task.status === "processing").length;
    },

    get failedTasks() {
      return this.tasks.filter((task) => task.status === "failed").length;
    },

    // Task management methods
    async refreshTasks() {
      this.loading = true;
      try {
        const tasks = await this.api.getTasks();
        this.tasks = tasks;
      } catch (error) {
        this.toastManager.showToast("Error loading tasks", "error");
        console.error("Error loading tasks:", error);
      } finally {
        this.loading = false;
      }
    },

    async selectTask(task) {
      this.selectedTask = task;
      this.taskFiles = [];
      this.taskSteps = [];

      document.body.classList.add("modal-open");

      try {
        // Load task files and steps
        if (task.output_directory) {
          const files = await this.api.getTaskFiles(task.id);
          this.taskFiles = files;
        }

        const steps = await this.api.getTaskSteps(task.id);
        this.taskSteps = steps;

        if (task.status === "completed") {
          let chosen = "";
          if (Array.isArray(this.taskFiles) && this.taskFiles.length > 0) {
            const indexFile = this.taskFiles.find((f) =>
              f.path.toLowerCase().endsWith("index.html")
            );
            if (indexFile) {
              chosen = indexFile.path;
            } else {
              const firstHTML = this.taskFiles.find((f) =>
                f.path.toLowerCase().endsWith(".html")
              );
              if (firstHTML) {
                chosen = firstHTML.path;
              }
            }
          }

          if (!!chosen) {
            this.viewTaskSteps = false;
          }
          this.showHTMLFile = chosen;
        } else {
          this.showHTMLFile = "";
          this.viewTaskSteps = true;
        }
      } catch (error) {
        console.error("Error loading task details:", error);
      }
    },

    closeTaskModal() {
      this.selectedTask = null;
      this.taskFiles = [];
      this.taskSteps = [];
      this.viewTaskSteps = true;
      document.body.classList.remove("modal-open");
    },

    toggleDetailView() {
      this.viewTaskSteps = !this.viewTaskSteps;
    },

    forceReconnect() {
      this.realtimeManager.forceReconnect();
    },

    isTaskLoadingShare(taskId) {
      // Simple implementation for now
      return false;
    },

    async uploadTaskFiles(taskId) {
      return this.uploadManager.uploadTaskFiles(taskId);
    },

    // Utility methods
    formatDate(dateString) {
      return Formatters.formatDate(dateString);
    },

    formatFileSize(bytes) {
      return Formatters.formatFileSize(bytes);
    },

    formatTimeAgo(date) {
      return Formatters.formatTimeAgo(date);
    },

    getStatusColor(status) {
      return (
        window.APP_CONFIG?.STATUS_COLORS[status] || "bg-gray-100 text-gray-800"
      );
    },

    getProgressColor(status) {
      return window.APP_CONFIG?.PROGRESS_COLORS[status] || "bg-gray-400";
    },

    getStepStatusColor(status) {
      return (
        window.APP_CONFIG?.STEP_STATUS_COLORS[status] ||
        "bg-gray-100 text-gray-600 border-gray-300"
      );
    },

    getStepStatusIcon(status) {
      return (
        window.APP_CONFIG?.STEP_STATUS_ICONS[status] ||
        "fas fa-clock text-gray-500"
      );
    },

    getStepTypeIcon(stepType) {
      return stepType === "plan" ? "🔍" : "🔨";
    },
  };
}

// Folder tree data function for Alpine.js compatibility
function createFolderTreeData() {
  return new FolderTreeManager();
}

// Initialize DOM utilities and observers when DOM is ready
document.addEventListener("DOMContentLoaded", function () {
  // Enable smooth scrolling
  document.documentElement.style.scrollBehavior = "smooth";

  // Setup button click animations
  DomUtils.setupButtonAnimation();
});

// Export globals for template compatibility
if (typeof window !== "undefined") {
  // Make functions available globally for Alpine.js
  window.dashboard = dashboard;
  window.createFolderTreeData = createFolderTreeData;
}
