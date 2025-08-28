// Task management functionality
class TaskManager {
  constructor(dashboard) {
    this.dashboard = dashboard;
    this.api = new ApiClient();
  }

  async refreshTasks() {
    this.dashboard.loading = true;
    try {
      const tasks = await this.api.getTasks();
      this.dashboard.tasks = tasks;
    } catch (error) {
      this.dashboard.toastManager.showToast("Error loading tasks", "error");
      console.error("Error loading tasks:", error);
    } finally {
      this.dashboard.loading = false;
    }
  }

  async selectTask(task) {
    this.dashboard.selectedTask = task;
    this.dashboard.taskFiles = [];
    this.dashboard.taskSteps = [];
    console.log("opening modal");
    document.body.classList.add("modal-open");

    const [file, step] = await Promise.all([
      task.output_directory ? this.loadTaskFiles(task.id) : Promise.resolve(),
      this.loadTaskSteps(task.id),
    ]);
    console.log("🚀 ~ TaskManager ~ selectTask ~ file, step:", { file, step });

    if (task.status === "completed") {
      let chosen = "";
      if (
        Array.isArray(this.dashboard.taskFiles) &&
        this.dashboard.taskFiles.length > 0
      ) {
        const indexFile = this.dashboard.taskFiles.find((f) =>
          f.path.toLowerCase().endsWith("index.html")
        );
        if (indexFile) {
          chosen = indexFile.path;
        } else {
          const firstHTML = this.dashboard.taskFiles.find((f) =>
            f.path.toLowerCase().endsWith(".html")
          );
          if (firstHTML) {
            chosen = firstHTML.path;
          }
        }
      }

      if (!!chosen) {
        this.dashboard.viewTaskSteps = false;
      }

      this.dashboard.showHTMLFile = chosen;
    } else {
      this.dashboard.showHTMLFile = "";
      this.dashboard.viewTaskSteps = true;
    }
  }

  closeTaskModal() {
    this.dashboard.selectedTask = null;
    this.dashboard.taskFiles = [];
    this.dashboard.taskSteps = [];
    this.dashboard.viewTaskSteps = true;
    document.body.classList.remove("modal-open");
  }

  async loadTaskFiles(taskId) {
    console.log("🚀 ~ TaskManager ~ loadTaskFiles ~ loadTaskFiles:");
    try {
      const files = await this.api.getTaskFiles(taskId);
      console.log("🚀 ~ TaskManager ~ loadTaskFiles ~ files:", files);
      this.dashboard.taskFiles = files;
    } catch (error) {
      console.error("Error loading task files:", error);
      this.dashboard.taskFiles = [];
    }
  }

  async loadTaskSteps(taskId) {
    try {
      const steps = await this.api.getTaskSteps(taskId);
      this.dashboard.taskSteps = steps;
    } catch (error) {
      console.error("Error loading task steps:", error);
      this.dashboard.taskSteps = [];
    }
  }

  async downloadTask(taskId) {
    try {
      const blob = await this.api.downloadTask(taskId);

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = `task-${taskId}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      this.dashboard.toastManager.showToast("Download started", "success");
    } catch (error) {
      this.dashboard.toastManager.showToast("Save error", "error");
      console.error("Download error:", error);
    }
  }

  updateTask(updatedTask) {
    const index = this.dashboard.tasks.findIndex(
      (t) => t.id === updatedTask.id
    );
    if (index !== -1) {
      this.dashboard.tasks[index] = updatedTask;

      if (
        this.dashboard.selectedTask &&
        this.dashboard.selectedTask.id === updatedTask.id
      ) {
        this.dashboard.selectedTask = updatedTask;
      }

      this.notifyTaskStatusChange(updatedTask);
    }
  }

  addTask(task) {
    // Check if task already exists
    const existingIndex = this.dashboard.tasks.findIndex(
      (t) => t.id === task.id
    );
    if (existingIndex === -1) {
      this.dashboard.tasks.unshift(task);
      this.dashboard.toastManager.showToast(
        `New task created: ${task.title}`,
        "info"
      );
    }
  }

  removeTask(taskId) {
    const index = this.dashboard.tasks.findIndex((t) => t.id === taskId);
    if (index !== -1) {
      const task = this.dashboard.tasks[index];
      this.dashboard.tasks.splice(index, 1);
      this.dashboard.toastManager.showToast(
        `Task deleted: ${task.title}`,
        "warning"
      );

      // Close modal if this task is currently selected
      if (this.dashboard.selectedTask?.id === taskId) {
        this.closeTaskModal();
      }
    }
  }

  notifyTaskStatusChange(task) {
    if (task.status === "completed") {
      this.dashboard.toastManager.showToast(
        `Task completed: ${task.title}`,
        "success"
      );
    }
    if (task.status === "failed") {
      this.dashboard.toastManager.showToast(
        `Task failed: ${task.title}`,
        "error"
      );
    }
  }

  previewFile(taskId, filePath) {
    const url = `./api/tasks/${taskId}/preview/${filePath}`;
    window.open(url, "_blank");
  }

  toggleDetailView() {
    this.dashboard.viewTaskSteps = !this.dashboard.viewTaskSteps;
  }

  // Computed getters
  getCompletedTasks() {
    return this.dashboard.tasks.filter((task) => task.status === "completed")
      .length;
  }

  getInProgressTasks() {
    return this.dashboard.tasks.filter((task) => task.status === "processing")
      .length;
  }

  getFailedTasks() {
    return this.dashboard.tasks.filter((task) => task.status === "failed")
      .length;
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.TaskManager = TaskManager;
}
