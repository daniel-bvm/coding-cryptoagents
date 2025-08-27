// Modal management functionality
class ModalManager {
  constructor(dashboard) {
    this.dashboard = dashboard;
  }

  openTaskModal(task) {
    this.dashboard.selectedTask = task;
    document.body.classList.add("modal-open");

    // Reset modal state
    this.dashboard.taskFiles = [];
    this.dashboard.taskSteps = [];
    this.dashboard.showHTMLFile = "";
    this.dashboard.viewTaskSteps = true;
  }

  closeTaskModal() {
    this.dashboard.selectedTask = null;
    this.dashboard.taskFiles = [];
    this.dashboard.taskSteps = [];
    this.dashboard.viewTaskSteps = true;
    this.dashboard.showHTMLFile = "";
    document.body.classList.remove("modal-open");
  }

  refreshTaskData(updatedTask) {
    if (this.dashboard.selectedTask?.id === updatedTask.id) {
      this.dashboard.selectedTask = updatedTask;

      // Refresh files and steps if needed
      if (updatedTask.status === "completed" && updatedTask.output_directory) {
        this.dashboard.taskManager.loadTaskFiles(updatedTask.id);
      }
    }
  }

  isModalOpen() {
    return !!this.dashboard.selectedTask;
  }

  getCurrentModalTask() {
    return this.dashboard.selectedTask;
  }

  setupModalEventListeners() {
    // Close modal on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isModalOpen()) {
        this.closeTaskModal();
      }
    });

    // Close modal on backdrop click (handled in template)
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.ModalManager = ModalManager;
}
