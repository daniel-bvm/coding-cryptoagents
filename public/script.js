// Dashboard functionality with real-time updates
function dashboard() {
  return {
    tasks: [],
    selectedTask: null,
    taskFiles: [],
    taskSteps: [],
    viewTaskSteps: true,
    loading: false,
    eventSource: null,
    planActivity: [],
    connectionStatus: "disconnected", // disconnected, connecting, connected
    reconnectAttempts: 0,
    reconnectTimeout: null,

    // Initialize the dashboard
    async init() {
      await this.refreshTasks();
      this.connectEventSource();
      this.setupEventListeners();
    },

    // Setup additional event listeners for connection management
    setupEventListeners() {
      // Reconnect when page becomes visible again
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden && this.connectionStatus === "disconnected") {
          console.log("Page became visible, attempting reconnection");
          this.connectEventSource();
        }
      });

      // Reconnect when network comes back online
      window.addEventListener("online", () => {
        console.log("Network came back online, attempting reconnection");
        if (this.connectionStatus === "disconnected") {
          this.connectEventSource();
        }
      });

      // Handle network offline
      window.addEventListener("offline", () => {
        console.log("Network went offline");
        this.connectionStatus = "disconnected";
        this.showConnectionToast("Network offline", "error");
        if (this.eventSource) {
          this.eventSource.close();
        }
      });
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

    // Fetch all tasks
    async refreshTasks() {
      this.loading = true;
      try {
        const response = await fetch("./api/tasks/");
        if (response.ok) {
          this.tasks = await response.json();
        } else {
          this.showToast("Failed to load tasks", "error");
        }
      } catch (error) {
        console.error("Error fetching tasks:", error);
        this.showToast("Error loading tasks", "error");
      } finally {
        this.loading = false;
      }
    },

    // Connect to real-time event stream
    connectEventSource() {
      if (this.eventSource) {
        this.eventSource.close();
      }

      // Show connection status
      this.connectionStatus = "connecting";
      this.showConnectionToast("Connecting to real-time updates...", "info");

      this.eventSource = new EventSource("/api/subscribe?channels=tasks");

      this.eventSource.onopen = () => {
        console.log("EventSource connected");
        this.connectionStatus = "connected";
        this.reconnectAttempts = 0;
        this.showConnectionToast("Connected to real-time updates", "success");
      };

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleRealtimeUpdate(data);
        } catch (error) {
          console.error("Error parsing event data:", error);
        }
      };

      this.eventSource.onerror = (error) => {
        console.error("EventSource error:", error);
        this.connectionStatus = "disconnected";
        this.eventSource.close();

        // Increment reconnect attempts
        this.reconnectAttempts = (this.reconnectAttempts || 0) + 1;

        // Fixed 2-second retry interval
        const delay = 2000; // Always 2 seconds

        // Show disconnection message
        this.showConnectionToast(
          `Connection lost. Reconnecting in 2s (attempt ${this.reconnectAttempts})`,
          "warning"
        );

        // Attempt to reconnect after 2 seconds
        this.reconnectTimeout = setTimeout(() => {
          this.connectEventSource();
        }, delay);
      };
    },

    // Handle real-time updates
    handleRealtimeUpdate(data) {
      const {
        event_type,
        task,
        task_id,
        step,
        step_number,
        title,
        total_steps,
        plan_summary,
      } = data.data;
      console.log("event data:", data.data);
      switch (event_type) {
        case "task_created":
          this.tasks.unshift(task);
          this.showToast(`New task created: ${task.title}`, "success");
          break;

        case "task_updated":
        case "task_progress":
        case "task_status":
        case "task_output":
          this.updateTask(task);
          break;

        case "task_deleted":
          this.tasks = this.tasks.filter((t) => t.id !== task_id);
          if (this.selectedTask && this.selectedTask.id === task_id) {
            this.selectedTask = null;
          }
          this.showToast("Task deleted", "info");
          break;

        case "plan_step_created":
          this.addPlanActivity({
            id: `step-${Date.now()}`,
            title: `Step ${step_number}: ${
              step.step_type === "plan" ? "Research" : "Build"
            }`,
            message: step.reason,
            details: `Task: ${title}`,
            icon: step.step_type === "plan" ? "🔍" : "🔨",
            timestamp: new Date(),
          });
          // also need to reload loadTaskSteps
          if (!!this.selectedTask) {
            this.loadTaskSteps(this.selectedTask.id);
          }

          this.showPlanStepNotification(step, step_number, title);
          break;

        case "plan_completed":
          this.addPlanActivity({
            id: `plan-${Date.now()}`,
            title: `Plan Ready: ${title}`,
            message: `Generated ${total_steps} steps (${plan_summary.plan_steps} research, ${plan_summary.build_steps} build)`,
            details: "Execution will begin shortly...",
            icon: "🎯",
            timestamp: new Date(),
          });

          this.showPlanCompletedNotification(title, total_steps, plan_summary);
          break;

        case "step_status_updated":
          this.updateStepStatus(data.data);
          break;
      }
    },

    // Update existing task
    updateTask(updatedTask) {
      const index = this.tasks.findIndex((t) => t.id === updatedTask.id);
      if (index !== -1) {
        this.tasks[index] = updatedTask;

        // Update selected task if it's the same
        if (this.selectedTask && this.selectedTask.id === updatedTask.id) {
          this.selectedTask = updatedTask;
          this.loadTaskFiles(updatedTask.id);
        }

        // Show progress notifications
        if (updatedTask.status === "completed") {
          this.showToast(`Task completed: ${updatedTask.title}`, "success");
        }
        if (updatedTask.status === "failed") {
          this.showToast(`Task failed: ${updatedTask.title}`, "error");
        }
      }
    },

    // Select a task and load its details
    async selectTask(task) {
      this.selectedTask = task;
      this.taskFiles = [];
      this.taskSteps = [];

      if (task.status === "completed") {
        this.viewTaskSteps = false;
      }

      // Load both files and steps
      await Promise.all([
        task.output_directory ? this.loadTaskFiles(task.id) : Promise.resolve(),
        this.loadTaskSteps(task.id),
      ]);
    },

    // Close task modal
    closeTaskModal() {
      this.selectedTask = null;
      this.taskFiles = [];
      this.taskSteps = [];
    },

    // Load files for a task
    async loadTaskFiles(taskId) {
      try {
        const response = await fetch(`./api/tasks/${taskId}/files`);
        if (response.ok) {
          const data = await response.json();
          this.taskFiles = data.files;
        }
      } catch (error) {
        console.error("Error loading task files:", error);
      }
    },

    // Load steps for a task
    async loadTaskSteps(taskId) {
      try {
        const response = await fetch(`./api/tasks/${taskId}/steps`);
        if (response.ok) {
          this.taskSteps = await response.json();
        } else {
          this.taskSteps = [];
        }
      } catch (error) {
        console.error("Error loading task steps:", error);
        this.taskSteps = [];
      }
    },

    // Download task as ZIP
    async downloadTask(taskId) {
      try {
        const response = await fetch(`./api/tasks/${taskId}/download`);
        if (response.ok) {
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `task_${taskId}.zip`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
          this.showToast("Download started", "success");
        } else {
          this.showToast("Download failed", "error");
        }
      } catch (error) {
        console.error("Error downloading task:", error);
        this.showToast("Download error", "error");
      }
    },

    // toggle detail view
    toggleDetailView() {
      console.log("Toggling detail view:", this.viewTaskSteps);
      this.viewTaskSteps = !this.viewTaskSteps;
    },

    // Preview a file
    previewFile(taskId, filePath) {
      const url = `./api/tasks/${taskId}/preview/${filePath}`;
      window.open(url, "_blank");
    },

    // Utility functions
    formatDate(dateString) {
      const date = new Date(dateString);
      return date.toLocaleString();
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

    // Plan activity management
    addPlanActivity(activity) {
      this.planActivity.unshift(activity);
      // Keep only last 20 activities
      if (this.planActivity.length > 20) {
        this.planActivity = this.planActivity.slice(0, 20);
      }
    },

    // Update step status in real-time
    updateStepStatus(data) {
      const { task_id, step_id, status, output } = data;

      // Update step in taskSteps if this task is currently selected
      if (this.selectedTask && this.selectedTask.id === task_id) {
        const stepIndex = this.taskSteps.findIndex(
          (step) => step.id === step_id
        );
        if (stepIndex !== -1) {
          this.taskSteps[stepIndex].status = status;
          if (output) {
            this.taskSteps[stepIndex].output = output;
          }
          if (status === "executing") {
            this.taskSteps[stepIndex].started_at = new Date().toISOString();
          } else if (status === "completed" || status === "failed") {
            this.taskSteps[stepIndex].completed_at = new Date().toISOString();
          }
        }
      }
    },

    // Get step status styling
    getStepStatusColor(status) {
      const colors = {
        pending: "bg-gray-100 text-gray-600 border-gray-300",
        executing: "bg-blue-100 text-blue-700 border-blue-300",
        completed: "bg-green-100 text-green-700 border-green-300",
        failed: "bg-red-100 text-red-700 border-red-300",
      };
      return colors[status] || colors.pending;
    },

    // Get step status icon
    getStepStatusIcon(status) {
      const icons = {
        pending: "fas fa-clock text-gray-500",
        executing: "fas fa-cog fa-spin text-blue-500",
        completed: "fas fa-check-circle text-green-500",
        failed: "fas fa-times-circle text-red-500",
      };
      return icons[status] || icons.pending;
    },

    // Get step type icon
    getStepTypeIcon(stepType) {
      return stepType === "plan" ? "🔍" : "🔨";
    },

    getStatusColor(status) {
      const colors = {
        pending: "bg-gray-100 text-gray-800",
        processing: "bg-blue-100 text-blue-800",
        completed: "bg-green-100 text-green-800",
        failed: "bg-red-100 text-red-800",
      };
      return colors[status] || "bg-gray-100 text-gray-800";
    },

    getStatusTextColor(status) {
      const colors = {
        pending: "text-gray-600",
        processing: "text-blue-600",
        completed: "text-green-600",
        failed: "text-red-600",
      };
      return colors[status] || "text-gray-600";
    },

    getProgressColor(status) {
      const colors = {
        pending: "bg-gray-400",
        processing: "bg-blue-500",
        completed: "bg-green-500",
        failed: "bg-red-500",
      };
      return colors[status] || "bg-gray-400";
    },

    // Show plan step creation notification
    showPlanStepNotification(step, stepNumber, title) {
      const stepTypeIcon = step.step_type === "plan" ? "🔍" : "🔨";
      const stepTypeText = step.step_type === "plan" ? "Research" : "Build";

      this.showAdvancedToast({
        title: `Step ${stepNumber}: ${stepTypeText}`,
        message: step.reason,
        type: "info",
        duration: 4000,
        icon: stepTypeIcon,
        details: `Task: ${title}`,
      });
    },

    // Show plan completion notification
    showPlanCompletedNotification(title, totalSteps, planSummary) {
      const planSteps = planSummary.plan_steps;
      const buildSteps = planSummary.build_steps;

      this.showAdvancedToast({
        title: `Plan Ready: ${title}`,
        message: `Generated ${totalSteps} steps (${planSteps} research, ${buildSteps} build)`,
        type: "success",
        duration: 6000,
        icon: "🎯",
        details: "Execution will begin shortly...",
      });
    },

    // Toast notification system
    showToast(message, type = "info") {
      const container = document.getElementById("toast-container");
      const toast = document.createElement("div");

      const icons = {
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

      toast.className = `flex items-center p-4 mb-2 border rounded-lg shadow-lg transform transition-all duration-300 ease-in-out translate-x-full opacity-0 ${colors[type]}`;
      toast.innerHTML = `
                <i class="${icons[type]} mr-3"></i>
                <span class="flex-1">${message}</span>
                <button onclick="this.parentElement.remove()" class="ml-3 text-gray-400 hover:text-gray-600">
                    <i class="fas fa-times"></i>
                </button>
            `;

      container.appendChild(toast);

      // Animate in
      setTimeout(() => {
        toast.classList.remove("translate-x-full", "opacity-0");
      }, 10);

      // Auto remove after 5 seconds
      setTimeout(() => {
        if (toast.parentElement) {
          toast.classList.add("translate-x-full", "opacity-0");
          setTimeout(() => {
            if (toast.parentElement) {
              toast.remove();
            }
          }, 300);
        }
      }, 5000);
    },

    // Connection status toast notifications
    showConnectionToast(message, type = "info") {
      // Remove any existing connection toasts first
      const existingToasts = document.querySelectorAll(".connection-toast");
      existingToasts.forEach((toast) => toast.remove());

      const container = document.getElementById("toast-container");
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
                    ? `<button onclick="this.parentElement.remove()" class="ml-2 text-gray-400 hover:text-gray-600">
                    <i class="fas fa-times text-xs"></i>
                </button>`
                    : ""
                }
            `;

      container.appendChild(toast);

      // Animate in
      setTimeout(() => {
        toast.classList.remove("translate-x-full", "opacity-0");
      }, 10);

      // Auto remove success messages after 3 seconds
      if (type === "success") {
        setTimeout(() => {
          if (toast.parentElement) {
            toast.classList.add("translate-x-full", "opacity-0");
            setTimeout(() => {
              if (toast.parentElement) {
                toast.remove();
              }
            }, 300);
          }
        }, 3000);
      }
    },

    // Advanced toast notification system for plan events
    showAdvancedToast({
      title,
      message,
      type = "info",
      duration = 5000,
      icon = null,
      details = null,
    }) {
      const container = document.getElementById("toast-container");
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
                <div class="absolute bottom-0 left-0 h-1 bg-current opacity-20 transition-all duration-${duration} ease-linear" style="width: 100%"></div>
            `;

      container.appendChild(toast);

      // Animate in
      setTimeout(() => {
        toast.classList.remove("translate-x-full", "opacity-0");
        // Start progress bar animation
        const progressBar = toast.querySelector(".absolute.bottom-0");
        if (progressBar) {
          setTimeout(() => {
            progressBar.style.width = "0%";
          }, 100);
        }
      }, 10);

      // Auto remove
      setTimeout(() => {
        if (toast.parentElement) {
          toast.classList.add("translate-x-full", "opacity-0");
          setTimeout(() => {
            if (toast.parentElement) {
              toast.remove();
            }
          }, 500);
        }
      }, duration);
    },

    // Cleanup on destroy
    destroy() {
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }
      this.connectionStatus = "disconnected";
    },

    // Manual reconnection function
    forceReconnect() {
      this.showConnectionToast("Manually reconnecting...", "info");
      this.destroy();
      this.connectEventSource();
    },
  };
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Add some smooth scrolling
  document.documentElement.style.scrollBehavior = "smooth";
});

// Add keyboard shortcuts
document.addEventListener("keydown", function (e) {
  // ESC to close modal
  if (e.key === "Escape") {
    const dashboardData = Alpine.store("dashboard");
    if (dashboardData && dashboardData.selectedTask) {
      dashboardData.selectedTask = null;
    }
  }
});

// Add some additional animations
const observerOptions = {
  threshold: 0.1,
  rootMargin: "0px 0px -50px 0px",
};

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = "1";
      entry.target.style.transform = "translateY(0)";
    }
  });
}, observerOptions);

// Observe elements for animation
document.addEventListener("DOMContentLoaded", () => {
  const animatedElements = document.querySelectorAll(".task-card");
  animatedElements.forEach((el) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(20px)";
    el.style.transition = "opacity 0.6s ease, transform 0.6s ease";
    observer.observe(el);
  });
});

// Add click animations
document.addEventListener("click", function (e) {
  if (e.target.matches("button") || e.target.closest("button")) {
    const button = e.target.matches("button")
      ? e.target
      : e.target.closest("button");
    button.style.transform = "scale(0.95)";
    setTimeout(() => {
      button.style.transform = "";
    }, 150);
  }
});
