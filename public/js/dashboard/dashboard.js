// Main dashboard application class
class Dashboard {
  constructor() {
    // Core state
    this.tasks = [];
    this.selectedTask = null;
    this.taskFiles = [];
    this.showHTMLFile = "";
    this.taskSteps = [];
    this.viewTaskSteps = true;
    this.loading = false;
    this.planActivity = [];

    // Initialize managers
    this.api = new ApiClient();
    this.toastManager = new ToastManager();
    this.taskManager = new TaskManager(this);
    this.realtimeManager = new RealtimeManager(this);
    this.modalManager = new ModalManager(this);
    this.uploadManager = new UploadManager(this);
    this.folderTree = new FolderTreeManager();
  }

  async init() {
    await this.taskManager.refreshTasks();
    this.realtimeManager.connect();
    this.setupEventListeners();
  }

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

    // Modal event listeners
    this.modalManager.setupModalEventListeners();
  }

  // Template rendering methods
  renderHeader() {
    return Templates.header(this);
  }

  renderStatsCards() {
    return Templates.statsCards();
  }

  renderTaskList() {
    return Templates.taskList();
  }

  renderModal() {
    return Templates.modal();
  }

  // Computed properties (for Alpine.js compatibility)
  get completedTasks() {
    return this.taskManager.getCompletedTasks();
  }

  get inProgressTasks() {
    return this.taskManager.getInProgressTasks();
  }

  get failedTasks() {
    return this.taskManager.getFailedTasks();
  }

  // Delegated methods for template compatibility
  async refreshTasks() {
    return this.taskManager.refreshTasks();
  }

  async selectTask(task) {
    return this.taskManager.selectTask(task);
  }

  closeTaskModal() {
    return this.taskManager.closeTaskModal();
  }

  async uploadTaskFiles(taskId) {
    return this.uploadManager.uploadTaskFiles(taskId);
  }

  isTaskLoadingShare(taskId) {
    return this.uploadManager.isTaskLoadingShare(taskId);
  }

  async downloadTask(taskId) {
    return this.taskManager.downloadTask(taskId);
  }

  previewFile(taskId, filePath) {
    return this.taskManager.previewFile(taskId, filePath);
  }

  toggleDetailView() {
    return this.taskManager.toggleDetailView();
  }

  forceReconnect() {
    return this.realtimeManager.forceReconnect();
  }

  // Utility methods for templates
  formatDate(dateString) {
    return Formatters.formatDate(dateString);
  }

  formatFileSize(bytes) {
    return Formatters.formatFileSize(bytes);
  }

  formatTimeAgo(date) {
    return Formatters.formatTimeAgo(date);
  }

  getStatusColor(status) {
    return (
      window.APP_CONFIG?.STATUS_COLORS[status] || "bg-gray-100 text-gray-800"
    );
  }

  getProgressColor(status) {
    return window.APP_CONFIG?.PROGRESS_COLORS[status] || "bg-gray-400";
  }

  getStepStatusColor(status) {
    return (
      window.APP_CONFIG?.STEP_STATUS_COLORS[status] ||
      "bg-gray-100 text-gray-600 border-gray-300"
    );
  }

  getStepStatusIcon(status) {
    return (
      window.APP_CONFIG?.STEP_STATUS_ICONS[status] ||
      "fas fa-clock text-gray-500"
    );
  }

  getStepTypeIcon(stepType) {
    return stepType === "plan" ? "🔍" : "🔨";
  }

  escapeHtmlInMarkdown(text) {
    return Formatters.escapeHtmlInMarkdown(text);
  }

  // Plan activity methods
  addPlanActivity(activity) {
    this.planActivity.unshift(activity);
    if (this.planActivity.length > 20) {
      this.planActivity = this.planActivity.slice(0, 20);
    }
  }

  updateStepStatus(data) {
    const { task_id, step_id, status, output } = data;

    if (this.selectedTask && this.selectedTask.id === task_id) {
      const step = this.taskSteps.find((s) => s.id === step_id);
      if (step) {
        step.status = status;
        if (output) {
          step.output = output;
        }
      }
    }
  }

  showPlanStepNotification(step, stepNumber, title) {
    const stepTypeIcon = step.step_type === "plan" ? "🔍" : "🔨";
    const stepTypeText = step.step_type === "plan" ? "Research" : "Build";

    this.toastManager.showAdvancedToast({
      title: `Step ${stepNumber}: ${stepTypeText}`,
      message: step.reason,
      type: "info",
      duration: 4000,
      icon: stepTypeIcon,
      details: `Task: ${title}`,
    });
  }

  showPlanCompletedNotification(title, totalSteps, planSummary) {
    const planSteps = planSummary.plan_steps;
    const buildSteps = planSummary.build_steps;

    this.toastManager.showAdvancedToast({
      title: `Plan Ready: ${title}`,
      message: `Generated ${totalSteps} steps (${planSteps} research, ${buildSteps} build)`,
      type: "success",
      duration: 6000,
      icon: "🎯",
      details: "Execution will begin shortly...",
    });
  }

  // Cleanup method
  destroy() {
    this.realtimeManager.disconnect();
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.Dashboard = Dashboard;
}
