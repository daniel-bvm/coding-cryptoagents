// Dashboard functionality with real-time updates
function dashboard() {
  return {
    tasks: [],
    selectedTask: null,
    taskFiles: [],
    showHTMLFile: "",
    taskSteps: [],
    viewTaskSteps: true,
    loading: false,
    eventSource: null,
    planActivity: [],
    connectionStatus: "disconnected", // disconnected, connecting, connected
    reconnectAttempts: 0,
    reconnectTimeout: null,
    loadingShares: {}, // Track loading state per task ID

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
        toastManager.showConnection("Network offline", "error");
        if (this.eventSource) {
          this.eventSource.close();
        }
      });
    },

    // Check if a specific task is loading share
    isTaskLoadingShare(taskId) {
      return !!this.loadingShares[taskId];
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
          toastManager.show("Failed to load tasks", "error");
        }
      } catch (error) {
        console.error("Error fetching tasks:", error);
        toastManager.show("Error loading tasks", "error");
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
      toastManager.showConnection("Connecting to real-time updates...", "info");

      this.eventSource = new EventSource("./api/subscribe?channels=tasks");

      this.eventSource.onopen = () => {
        console.log("EventSource connected");
        this.connectionStatus = "connected";
        this.reconnectAttempts = 0;
        toastManager.showConnection(
          "Connected to real-time updates",
          "success"
        );
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

        // Show disconnection message
        toastManager.showConnection(
          `Connection lost. Reconnecting in 2s (attempt ${this.reconnectAttempts})`,
          "warning"
        );

        // Attempt to reconnect after 2 seconds
        this.reconnectTimeout = setTimeout(() => {
          this.connectEventSource();
        }, CONSTANTS.RECONNECT_DELAY);
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
          toastManager.show(`New task created: ${task.title}`, "success");
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
            document.body.classList.remove("modal-open");
          }
          toastManager.show("Task deleted", "info");
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

          // Reload task steps if task is selected
          if (this.selectedTask) {
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
          toastManager.show(`Task completed: ${updatedTask.title}`, "success");
        }
        if (updatedTask.status === "failed") {
          toastManager.show(`Task failed: ${updatedTask.title}`, "error");
        }
      }
    },

    // Select a task and load its details
    async selectTask(task) {
      this.selectedTask = task;
      this.taskFiles = [];
      this.taskSteps = [];

      // Add modal-open class to body to hide scrollbar
      document.body.classList.add("modal-open");

      // Load both files and steps
      await Promise.all([
        task.output_directory ? this.loadTaskFiles(task.id) : Promise.resolve(),
        this.loadTaskSteps(task.id),
      ]);

      if (task.status === "completed") {
        // Choose an HTML file to show: prefer index.html, otherwise first .html, else empty
        const chosen = utils.findBestHtmlFile(this.taskFiles);

        if (chosen) {
          this.viewTaskSteps = false;
        }

        this.showHTMLFile = chosen || "";
      } else {
        this.showHTMLFile = "";
        this.viewTaskSteps = true;
      }
    },

    // Close task modal
    closeTaskModal() {
      this.selectedTask = null;
      this.taskFiles = [];
      this.taskSteps = [];

      // Remove modal-open class from body to restore scrollbar
      document.body.classList.remove("modal-open");
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
    // Save the content to local folder (stream download as ZIP)
    async downloadTask(taskId) {
      try {
        const response = await fetch(`./api/tasks/${taskId}/download`);
        if (response.ok) {
          // Use the File System Access API if available
          if ("showSaveFilePicker" in window) {
            try {
              const options = {
                suggestedName: `task_${taskId}.zip`,
                types: [
                  {
                    description: "ZIP file",
                    accept: { "application/zip": [".zip"] },
                  },
                ],
              };
              const handle = await window.showSaveFilePicker(options);
              const writable = await handle.createWritable();

              if (response.body && writable) {
                // Stream directly from response to file
                await response.body.pipeTo(writable);
                toastManager.show("Saved to local folder", "success");
              } else {
                // Fallback if streaming not supported
                const blob = await response.blob();
                await writable.write(blob);
                await writable.close();
                toastManager.show("Saved to local folder", "success");
              }
            } catch (fsError) {
              // If user cancels or error, fallback to download
              this.fallbackDownload(await response.blob(), taskId);
            }
          } else {
            // Fallback for browsers without File System Access API
            this.fallbackDownload(await response.blob(), taskId);
          }
        } else {
          toastManager.show("Download failed", "error");
        }
      } catch (error) {
        console.error("Error saving task:", error);
        toastManager.show("Save error", "error");
      }
    },

    // Fallback download method
    fallbackDownload(blob, taskId) {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `task_${taskId}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toastManager.show("Download started", "success");
    },

    // Helper method to find the best HTML file to share
    findBestHtmlFile() {
      return utils.findBestHtmlFile(this.taskFiles);
    },

    // Helper method to copy share link to clipboard
    async copyShareLink(baseUrl, filePath) {
      const shareUrl = `${baseUrl}/${filePath}`;
      try {
        if (await utils.copyToClipboard(shareUrl)) {
          toastManager.show("Share link copied to clipboard", "success");
        } else {
          // If copy failed, show the URL in a toast so user can copy manually
          toastManager.showAdvanced({
            title: "Copy manually",
            message: "Couldn't copy automatically. Click to select:",
            type: "info",
            duration: 10000,
            details: shareUrl
          });
        }
      } catch (error) {
        console.error("Error copying to clipboard:", error);
        toastManager.showAdvanced({
          title: "Share Link Ready",
          message: "Please copy manually:",
          type: "info",
          duration: 10000,
          details: shareUrl
        });
      }
    },

    // From taskId, upload its taskFiles to CDN (API provided later), after upload success, return url contain index.html or first html file available
    async uploadTaskFiles(taskId) {
      try {
        this.loadingShares[taskId] = true;

        // Ensure task files are loaded
        if (!this.taskFiles || this.taskFiles.length === 0) {
          await this.loadTaskFiles(taskId);
        }

        if (!this.taskFiles || this.taskFiles.length === 0) {
          toastManager.show("No files to upload", "error");
          return null;
        }

        // Check if deployment already exists on EternalAI
        const chosenFile = this.findBestHtmlFile();

        try {
          const checkResponse = await fetch(
            `${CONSTANTS.CDN_BASE_URL}/${taskId}/${chosenFile}`
          );
          if (checkResponse.ok) {
            // Files already exist, use existing deployment
            const baseUrl = `${CONSTANTS.CDN_BASE_URL}/${taskId}`;
            return await this.handleExistingCdnLink(baseUrl);
          }
        } catch (error) {
          // Deployment doesn't exist, proceed with upload
          console.log("No existing deployment found, proceeding with upload");
        }

        // No existing deployment, proceed with upload
        return await this.uploadNewFiles(taskId);
      } catch (error) {
        console.error("Error uploading task files:", error);
        toastManager.show("Upload failed", "error");
        return null;
      } finally {
        delete this.loadingShares[taskId];
      }
    },

    // Handle existing CDN link
    async handleExistingCdnLink(existingUrl) {
      const chosenFile = this.findBestHtmlFile();

      if (!chosenFile) {
        toastManager.show("No HTML file to share", "error");
        return null;
      }

      await this.copyShareLink(existingUrl, chosenFile);
      return existingUrl;
    },

    // Create ZIP file from task files
    async createZipFromTaskFiles(taskId) {
      try {
        // use API
        const response = await fetch(`./api/tasks/${taskId}/download`);
        if (response.ok) {
          return await response.blob();
        } else {
          console.error("Failed to create ZIP file:", response.statusText);
          return null;
        }
      } catch (error) {
        console.error("Error creating ZIP file:", error);
        return null;
      }
    },

    // Upload new files to CDN
    async uploadNewFiles(taskId) {
      try {
        // First, create a ZIP file from task files
        const zipBlob = await this.createZipFromTaskFiles(taskId);
        if (!zipBlob) {
          toastManager.show("Failed to create ZIP file", "error");
          return null;
        }

        // Upload ZIP to EternalAI API
        const formData = new FormData();
        formData.append("file", zipBlob, `${taskId}.zip`);
        formData.append("folder_name", taskId);

        const response = await fetch(
          "https://api.eternalai.org/api/agent/file/upload-zip-extract?admin_key=eai2024",
          {
            method: "POST",
            body: formData,
          }
        );

        if (!response.ok) {
          console.error("Upload failed:", response.statusText);
          toastManager.show("Upload failed", "error");
          return null;
        }

        const data = await response.json();
        toastManager.show("Deployment successful", "success");

        const chosenFile = this.findBestHtmlFile();
        if (!chosenFile) {
          toastManager.show("No HTML file to share", "error");
          return null;
        }

        // Construct the URL based on EternalAI's response structure
        const baseUrl = data.url || `https://api.eternalai.org/files/${taskId}`;
        await this.copyShareLink(baseUrl, chosenFile);
        return baseUrl;
      } catch (error) {
        console.error("Upload error:", error);
        toastManager.show("Upload failed", "error");
        return null;
      }
    },

    // toggle detail view
    toggleDetailView() {
      this.viewTaskSteps = !this.viewTaskSteps;
    },

    // Preview a file
    previewFile(taskId, filePath) {
      const url = `./api/tasks/${taskId}/preview/${filePath}`;
      window.open(url, "_blank");
    },

    // Utility functions (delegated to utils)
    formatDate: utils.formatDate,
    formatFileSize: utils.formatFileSize,
    formatTimeAgo: utils.formatTimeAgo,
    escapeHtmlInMarkdown: utils.escapeHtmlInMarkdown,
    getStepTypeIcon: utils.getStepTypeIcon,

    // Plan activity management
    addPlanActivity(activity) {
      this.planActivity.unshift(activity);
      // Keep only last activities
      if (this.planActivity.length > CONSTANTS.MAX_PLAN_ACTIVITIES) {
        this.planActivity = this.planActivity.slice(
          0,
          CONSTANTS.MAX_PLAN_ACTIVITIES
        );
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
      return STEP_CONFIGS.colors[status] || STEP_CONFIGS.colors.pending;
    },

    // Get step status icon
    getStepStatusIcon(status) {
      return STEP_CONFIGS.icons[status] || STEP_CONFIGS.icons.pending;
    },

    // Get status styling
    getStatusColor(status) {
      return STATUS_CONFIGS.colors[status] || STATUS_CONFIGS.colors.pending;
    },

    // Get progress color
    getProgressColor(status) {
      return (
        STATUS_CONFIGS.progressColors[status] ||
        STATUS_CONFIGS.progressColors.pending
      );
    },

    // Get status text color for task details
    getStatusTextColor(status) {
      return (
        STATUS_CONFIGS.textColors[status] || STATUS_CONFIGS.textColors.pending
      );
    },

    // Show plan step creation notification
    showPlanStepNotification(step, stepNumber, title) {
      const stepTypeIcon = step.step_type === "plan" ? "🔍" : "🔨";
      const stepTypeText = step.step_type === "plan" ? "Research" : "Build";

      toastManager.showAdvanced({
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

      toastManager.showAdvanced({
        title: `Plan Ready: ${title}`,
        message: `Generated ${totalSteps} steps (${planSteps} research, ${buildSteps} build)`,
        type: "success",
        duration: 6000,
        icon: "🎯",
        details: "Execution will begin shortly...",
      });
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
      toastManager.showConnection("Manually reconnecting...", "info");
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
