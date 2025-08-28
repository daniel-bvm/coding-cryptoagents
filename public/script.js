const CDN_BASE_URL = "https://cdn.eternalai.org/prototype-agent";

// Update according to your agent
const CONFIG = {
  AGENT_ID: "15873", // Set your actual agent ID
  AGENT_SLUG: "9003-prototype", // Set your actual agent slug
};

// Shared constants and utilities
const SHARED_CONSTANTS = {
  DEFAULT_GREETING_MESSAGE: `[{"role":"assistant","content":"Hi, I'm Prototype agent, specialized in building websites, reports and blogs.\\n\\n\\"Research the latest trends in AI and create a blog post about it.\\"\\n\\"Build an interactive report about climate change with charts and visuals.\\"\\n\\"Plan and build a landing page for a crypto exchange named Binance\\"\\n\\nJust tell me, what do you want to create?"}]`,
  SHARED_AGENT_CHAT_API:
    "https://api-dojo2.eternalai.org/api/shared-agent-chat",
  TOAST_DURATION: {
    DEFAULT: 5000,
    CONNECTION: 3000,
    ADVANCED: 5000,
    SUCCESS_EXTENDED: 6000,
  },
};

// Utility functions
const utils = {
  // API Helper
  async makeApiCall(url, options = {}) {
    try {
      const response = await fetch(url, {
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...options.headers,
        },
        ...options,
      });
      return response.ok ? response : null;
    } catch (error) {
      console.error(`API call failed: ${url}`, error);
      return null;
    }
  },

  // HTML file finding logic
  findBestHtmlFile(taskFiles) {
    if (!Array.isArray(taskFiles) || taskFiles.length === 0) {
      return null;
    }

    const indexFile = taskFiles.find((f) =>
      f.path.toLowerCase().endsWith("index.html")
    );
    if (indexFile) {
      return indexFile.path;
    }

    const firstHTML = taskFiles.find((f) =>
      f.path.toLowerCase().endsWith(".html")
    );
    return firstHTML ? firstHTML.path : null;
  },

  // Status color mappings
  getStatusColor(status) {
    const colors = {
      pending: "bg-gray-100 text-gray-800",
      processing: "bg-blue-100 text-blue-800",
      completed: "bg-green-100 text-green-800",
      failed: "bg-red-100 text-red-800",
    };
    return colors[status] || "bg-gray-100 text-gray-800";
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

  getStatusTextColor(status) {
    const colors = {
      pending: "text-gray-600",
      processing: "text-blue-600",
      completed: "text-green-600",
      failed: "text-red-600",
    };
    return colors[status] || "text-gray-600";
  },

  getStepStatusColor(status) {
    const colors = {
      pending: "bg-gray-100 text-gray-600 border-gray-300",
      executing: "bg-blue-100 text-blue-700 border-blue-300",
      completed: "bg-green-100 text-green-700 border-green-300",
      failed: "bg-red-100 text-red-700 border-red-300",
    };
    return colors[status] || colors.pending;
  },

  getStepStatusIcon(status) {
    const icons = {
      pending: "fas fa-clock text-gray-500",
      executing: "fas fa-cog fa-spin text-blue-500",
      completed: "fas fa-check-circle text-green-500",
      failed: "fas fa-times-circle text-red-500",
    };
    return icons[status] || icons.pending;
  },

  getStepTypeIcon(stepType) {
    return stepType === "plan" || stepType === "research" ? "🔍" : "🔨";
  },

  // Shared link creation
  async createSharedLink(taskId, chosenFile) {
    // const userPrompt = await utils
    //   .makeApiCall(`/api/tasks/${taskId}/messages`)
    //   .then((res) => res.json())
    //   .then((data) => data?.messages?.[0]?.content || "");

    // console.log("🚀 ~ createSharedLink ~ userPrompt:", userPrompt);

    let shareMessage = SHARED_CONSTANTS.DEFAULT_GREETING_MESSAGE;

    // if (userPrompt && userPrompt.trim() !== "") {
    //   shareMessage = userPrompt;
    // }

    const response = await utils.makeApiCall(
      SHARED_CONSTANTS.SHARED_AGENT_CHAT_API,
      {
        method: "POST",
        body: JSON.stringify({
          wallet_address: taskId,
          shared_message: shareMessage,
          processing_url: `${CDN_BASE_URL}/${taskId}/${chosenFile}`,
          agent_id: CONFIG.AGENT_ID,
        }),
      }
    );

    if (response) {
      const data = await response.json();
      const shareId = data.data.unique_number;
      return `https://eternalai.org/${CONFIG.AGENT_SLUG}/${shareId}`;
    }
    return null;
  },

  // Format utilities
  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  },

  formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
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

  escapeHtmlInMarkdown(text) {
    return text.replace(/<(\w+)>/g, "`<$1>`");
  },
};

// Toast utility functions
const toastUtils = {
  getContainer() {
    return document.getElementById("toast-container");
  },

  createToast(content, className) {
    const toast = document.createElement("div");
    toast.className = className;
    toast.innerHTML = content;
    return toast;
  },

  showToast(
    toast,
    container,
    duration = SHARED_CONSTANTS.TOAST_DURATION.DEFAULT
  ) {
    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.remove("translate-x-full", "opacity-0");
    }, 10);

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
  },

  getToastColors(type) {
    return (
      {
        success: "bg-green-50 border-green-200 text-green-800",
        error: "bg-red-50 border-red-200 text-red-800",
        info: "bg-blue-50 border-blue-200 text-blue-800",
        warning: "bg-yellow-50 border-yellow-200 text-yellow-800",
      }[type] || "bg-blue-50 border-blue-200 text-blue-800"
    );
  },

  getToastIcons(type) {
    return (
      {
        success: "fas fa-check-circle text-green-500",
        error: "fas fa-exclamation-circle text-red-500",
        info: "fas fa-info-circle text-blue-500",
        warning: "fas fa-exclamation-triangle text-yellow-500",
      }[type] || "fas fa-info-circle text-blue-500"
    );
  },
};

// Folder tree utility functions
function createFolderTreeData() {
  return {
    collapsedFolders: {},

    buildFolderTree(taskFiles) {
      const tree = { folders: {}, files: [] };

      taskFiles.forEach((file) => {
        const parts = file.path.split("/");
        const fileName = parts.pop();

        if (parts.length === 0) {
          tree.files.push({ ...file, name: fileName });
          return;
        }

        let current = tree;
        let currentPath = "";

        parts.forEach((part, index) => {
          currentPath += (index > 0 ? "/" : "") + part;

          if (!current.folders[part]) {
            current.folders[part] = {
              name: part,
              path: currentPath,
              folders: {},
              files: [],
            };
          }
          current = current.folders[part];
        });

        current.files.push({ ...file, name: fileName });
      });

      return tree;
    },

    toggleFolder(folderPath) {
      // If folder path doesn't exist, it means it's collapsed by default, so we expand it
      if (this.collapsedFolders[folderPath] === undefined) {
        this.collapsedFolders[folderPath] = false; // expanded
      } else {
        this.collapsedFolders[folderPath] = !this.collapsedFolders[folderPath];
      }
    },

    isFolderCollapsed(folderPath) {
      // Return true (collapsed) by default if folder state is not set
      return this.collapsedFolders[folderPath] !== false;
    },

    renderTree(tree, depth = 0) {
      let items = [];

      // Add files at current level
      tree.files.forEach((file) => {
        items.push({
          type: "file",
          data: file,
          depth: depth,
        });
      });

      // Add folders at current level
      Object.entries(tree.folders).forEach(([folderName, folder]) => {
        items.push({
          type: "folder",
          data: folder,
          depth: depth,
        });

        // If folder is not collapsed, add its contents
        if (!this.isFolderCollapsed(folder.path)) {
          items.push(...this.renderTree(folder, depth + 1));
        }
      });

      return items;
    },

    getAllItems(taskFiles) {
      return this.renderTree(this.buildFolderTree(taskFiles));
    },
  };
}

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
    connectionStatus: "disconnected",
    reconnectAttempts: 0,
    reconnectTimeout: null,
    loadingShares: {},

    // Share link cache to avoid redundant API calls
    shareLinkCache: new Map(),

    // Folder tree instance
    folderTree: createFolderTreeData(),

    uploadConfig: {
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
    },
    async init() {
      await this.refreshTasks();
      this.connectEventSource();
      this.setupEventListeners();
    },

    setupEventListeners() {
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden && this.connectionStatus === "disconnected") {
          this.connectEventSource();
        }
      });

      window.addEventListener("online", () => {
        if (this.connectionStatus === "disconnected") {
          this.connectEventSource();
        }
      });

      window.addEventListener("offline", () => {
        this.connectionStatus = "disconnected";
        this.showConnectionToast("Network offline", "error");
        if (this.eventSource) {
          this.eventSource.close();
        }
      });
    },
    isTaskLoadingShare(taskId) {
      return !!this.loadingShares[taskId];
    },

    get completedTasks() {
      return this.tasks.filter((task) => task.status === "completed").length;
    },

    get inProgressTasks() {
      return this.tasks.filter((task) => task.status === "processing").length;
    },

    get failedTasks() {
      return this.tasks.filter((task) => task.status === "failed").length;
    },

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
        this.showToast("Error loading tasks", "error");
      } finally {
        this.loading = false;
      }
    },

    connectEventSource() {
      if (this.eventSource) {
        this.eventSource.close();
      }

      this.connectionStatus = "connecting";
      this.showConnectionToast("Connecting to real-time updates...", "info");

      this.eventSource = new EventSource("./api/subscribe?channels=tasks");

      this.eventSource.onopen = () => {
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
        this.connectionStatus = "disconnected";
        this.eventSource.close();

        this.reconnectAttempts = (this.reconnectAttempts || 0) + 1;

        const delay = 2000;

        this.showConnectionToast(
          `Connection lost. Reconnecting in 2s (attempt ${this.reconnectAttempts})`,
          "warning"
        );

        this.reconnectTimeout = setTimeout(() => {
          this.connectEventSource();
        }, delay);
      };
    },
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
          // Clear cached share link for deleted task
          this.shareLinkCache.delete(task_id);
          if (this.selectedTask && this.selectedTask.id === task_id) {
            this.selectedTask = null;
            document.body.classList.remove("modal-open");
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

    updateTask(updatedTask) {
      const index = this.tasks.findIndex((t) => t.id === updatedTask.id);
      if (index !== -1) {
        this.tasks[index] = updatedTask;

        if (this.selectedTask && this.selectedTask.id === updatedTask.id) {
          this.selectedTask = updatedTask;
          this.loadTaskFiles(updatedTask.id);
        }

        if (updatedTask.status === "completed") {
          this.showToast(`Task completed: ${updatedTask.title}`, "success");
        }
        if (updatedTask.status === "failed") {
          this.showToast(`Task failed: ${updatedTask.title}`, "error");
        }
      }
    },

    async selectTask(task) {
      this.selectedTask = task;
      this.taskFiles = [];
      this.taskSteps = [];

      document.body.classList.add("modal-open");

      await Promise.all([
        task.output_directory ? this.loadTaskFiles(task.id) : Promise.resolve(),
        this.loadTaskSteps(task.id),
      ]);

      if (task.status === "completed") {
        const chosen = this.findBestHtmlFile();
        if (chosen) {
          this.viewTaskSteps = false;
        }
        this.showHTMLFile = chosen || "";
      } else {
        this.showHTMLFile = "";
        this.viewTaskSteps = true;
      }
    },
    closeTaskModal() {
      this.selectedTask = null;
      this.taskFiles = [];
      this.taskSteps = [];
      this.viewTaskSteps = true;
      document.body.classList.remove("modal-open");
    },

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

    async loadTaskSteps(taskId) {
      try {
        const response = await fetch(`./api/tasks/${taskId}/steps`);
        if (response.ok) {
          this.taskSteps = await response.json();
        } else {
          this.taskSteps = [];
        }
      } catch (error) {
        this.taskSteps = [];
      }
    },

    async downloadTask(taskId) {
      try {
        const response = await fetch(`./api/tasks/${taskId}/download`);
        if (response.ok) {
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
                await response.body.pipeTo(writable);
                this.showToast("Saved to local folder", "success");
              } else {
                const blob = await response.blob();
                await writable.write(blob);
                await writable.close();
                this.showToast("Saved to local folder", "success");
              }
            } catch (fsError) {
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
            }
          } else {
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
          }
        } else {
          this.showToast("Download failed", "error");
        }
      } catch (error) {
        this.showToast("Save error", "error");
      }
    },
    findBestHtmlFile() {
      return utils.findBestHtmlFile(this.taskFiles);
    },

    async copyShareLink(shareUrl) {
      // const shareUrl = `${baseUrl}/${filePath}`;
      try {
        await navigator.clipboard.writeText(shareUrl);
        this.showToast("Share link copied to clipboard", "success");
      } catch (err) {
        console.error("Failed to copy share link:", err);
      }
    },

    async uploadTaskFiles(taskId) {
      try {
        this.loadingShares[taskId] = true;

        // Check if we already have a cached share link for this task
        if (this.shareLinkCache.has(taskId)) {
          const cachedShareUrl = this.shareLinkCache.get(taskId);
          return await this.copyShareLink(cachedShareUrl);
        }

        if (!this.taskFiles || this.taskFiles.length === 0) {
          await this.loadTaskFiles(taskId);
        }

        if (!this.taskFiles || this.taskFiles.length === 0) {
          this.showToast("No files to upload", "error");
          return null;
        }
        const chosenFile = this.findBestHtmlFile();

        const checkResponse = await fetch(
          `${CDN_BASE_URL}/${taskId}/${chosenFile}`
        );
        if (checkResponse.ok) {
          const shareUrl = await utils.createSharedLink(taskId, chosenFile);
          if (shareUrl) {
            // Cache the share link for future use
            this.shareLinkCache.set(taskId, shareUrl);
            return await this.copyShareLink(shareUrl);
          } else {
            this.showToast("Failed to create shared link", "error");
          }
        }

        return await this.uploadNewFiles(taskId);
      } catch (error) {
        this.showToast("Upload failed", "error");
        return null;
      } finally {
        delete this.loadingShares[taskId];
      }
    },

    async createZipFromTaskFiles(taskId) {
      try {
        const response = await fetch(`./api/tasks/${taskId}/download`);
        if (response.ok) {
          const zipBlob = await response.blob();
          return zipBlob;
        } else {
          return null;
        }
      } catch (error) {
        return null;
      }
    },

    async uploadNewFiles(taskId) {
      let progressToastId = null;
      try {
        const startTime = Date.now();
        progressToastId = this.showProgressToast("Preparing deployment...", 0);
        await this.ensureMinimumStepTime(
          startTime,
          this.uploadConfig.minimumStepTimes.preparation,
          progressToastId
        );

        const zipStartTime = Date.now();
        this.updateProgressToast(
          progressToastId,
          "Creating deployment package...",
          5
        );
        const zipBlob = await this.createZipFromTaskFiles(taskId);
        if (!zipBlob) {
          this.showToast("Failed to create deployment package", "error");
          return null;
        }
        await this.ensureMinimumStepTime(
          zipStartTime,
          this.uploadConfig.minimumStepTimes.zipCreation,
          progressToastId
        );

        const fileSizeFormatted = this.formatFileSize(zipBlob.size);

        const analysisStartTime = Date.now();
        this.updateProgressToast(
          progressToastId,
          `Analyzing package (${fileSizeFormatted})...`,
          5
        );
        await this.ensureMinimumStepTime(
          analysisStartTime,
          this.uploadConfig.minimumStepTimes.analysis,
          progressToastId
        );

        let uploadResult = await this.uploadFileWhole(
          taskId,
          zipBlob,
          progressToastId
        );

        if (!uploadResult) {
          this.hideProgressToast(progressToastId);
          this.showToast("Upload failed", "error");
          return null;
        }

        const chosenFile = this.findBestHtmlFile();
        if (!chosenFile) {
          this.showToast("No HTML file to share", "error");
          return null;
        }
        const folderPath = uploadResult.data.folder_path;
        const baseUrl = folderPath ? folderPath : `${CDN_BASE_URL}/${taskId}`;

        if (baseUrl) {
          const shareUrl = await utils.createSharedLink(taskId, chosenFile);
          if (shareUrl) {
            // Cache the share link for future use
            this.shareLinkCache.set(taskId, shareUrl);
            await this.copyShareLink(shareUrl);
          }
        }

        return baseUrl;
      } catch (error) {
        if (progressToastId) {
          this.hideProgressToast(progressToastId);
        }
        console.log("Upload failed", error);
        this.showToast("Upload failed", error.message);
        return null;
      } finally {
        this.hideProgressToast(progressToastId);
      }
    },

    async uploadFileWhole(taskId, fileBlob, progressToastId) {
      const fileSizeFormatted = this.formatFileSize(fileBlob.size);
      const startTime = Date.now();

      try {
        this.updateProgressToast(
          progressToastId,
          `Preparing upload (${fileSizeFormatted})...`,
          10
        );
        await this.ensureMinimumStepTime(
          startTime,
          this.uploadConfig.minimumStepTimes.uploadPrep,
          progressToastId
        );

        const uploadStartTime = Date.now();
        this.updateProgressToast(
          progressToastId,
          `Uploading file (${fileSizeFormatted})...`,
          20
        );

        const formData = new FormData();
        formData.append("file", fileBlob, `${taskId}.zip`);
        formData.append("folder_name", taskId);

        const uploadPromise = new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          let lastProgressUpdate = Date.now();

          xhr.upload.addEventListener("progress", (e) => {
            const now = Date.now();
            if (now - lastProgressUpdate >= 200 && e.lengthComputable) {
              const uploadProgress = Math.round((e.loaded / e.total) * 60) + 20;
              this.updateProgressToast(
                progressToastId,
                `Uploading... (${this.formatFileSize(
                  e.loaded
                )}/${fileSizeFormatted})`,
                uploadProgress
              );
              lastProgressUpdate = now;
            }
          });

          xhr.addEventListener("load", () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(JSON.parse(xhr.responseText));
            } else {
              reject(new Error(`Upload failed: ${xhr.statusText}`));
            }
          });

          xhr.addEventListener("error", () => {
            reject(new Error("Upload failed due to network error"));
          });

          xhr.open("POST", "./api/upload/single");
          xhr.send(formData);
        });

        await this.ensureMinimumStepTime(
          uploadStartTime,
          this.uploadConfig.minimumStepTimes.uploadStep,
          progressToastId
        );

        const processingStartTime = Date.now();
        this.updateProgressToast(progressToastId, "Processing upload...", 80);

        const result = await uploadPromise;

        await this.ensureMinimumStepTime(
          processingStartTime,
          this.uploadConfig.minimumStepTimes.processing,
          progressToastId
        );

        const extractionStartTime = Date.now();
        this.updateProgressToast(progressToastId, "Extracting files...", 90);
        await this.ensureMinimumStepTime(
          extractionStartTime,
          this.uploadConfig.minimumStepTimes.extraction,
          progressToastId
        );

        this.updateProgressToast(
          progressToastId,
          "Upload completed successfully!",
          100
        );
        this.hideProgressToast(progressToastId);
        console.log("🚀 ~ uploadFileWhole ~ result:", result);

        if (result) return result;
      } catch (error) {
        this.updateProgressToast(
          progressToastId,
          `Upload failed: ${error.message}`,
          -1
        );
        throw error;
      }
    },

    async ensureMinimumStepTime(stepStartTime, minimumMs, toastId = null) {
      if (!this.uploadConfig.enforceMinimumStepTiming) {
        return;
      }

      const elapsed = Date.now() - stepStartTime;
      if (elapsed < minimumMs) {
        const remainingTime = minimumMs - elapsed;
        await this.delay(remainingTime);
      }
    },

    toggleMinimumStepTiming() {
      this.uploadConfig.enforceMinimumStepTiming =
        !this.uploadConfig.enforceMinimumStepTiming;
      this.showToast(
        `Minimum step timing ${
          this.uploadConfig.enforceMinimumStepTiming ? "enabled" : "disabled"
        }`,
        "info"
      );
    },

    delay(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    },

    toggleDetailView() {
      this.viewTaskSteps = !this.viewTaskSteps;
    },

    previewFile(taskId, filePath) {
      const url = `./api/tasks/${taskId}/preview/${filePath}`;
      window.open(url, "_blank");
    },

    formatDate(dateString) {
      return utils.formatDate(dateString);
    },

    formatFileSize(bytes) {
      return utils.formatFileSize(bytes);
    },

    formatTimeAgo(date) {
      return utils.formatTimeAgo(date);
    },

    addPlanActivity(activity) {
      this.planActivity.unshift(activity);
      if (this.planActivity.length > 20) {
        this.planActivity = this.planActivity.slice(0, 20);
      }
    },

    updateStepStatus(data) {
      const { task_id, step_id, status, output } = data;

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

    getStepStatusColor(status) {
      return utils.getStepStatusColor(status);
    },

    getStepStatusIcon(status) {
      return utils.getStepStatusIcon(status);
    },

    getStepTypeIcon(stepType) {
      return utils.getStepTypeIcon(stepType);
    },

    getStatusColor(status) {
      return utils.getStatusColor(status);
    },

    escapeHtmlInMarkdown(text) {
      return utils.escapeHtmlInMarkdown(text);
    },

    getProgressColor(status) {
      return utils.getProgressColor(status);
    },

    getStatusTextColor(status) {
      return utils.getStatusTextColor(status);
    },

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

    showToast(message, type = "info") {
      const container = toastUtils.getContainer();
      const colors = toastUtils.getToastColors(type);
      const icon = toastUtils.getToastIcons(type);

      const content = `
        <i class="${icon} mr-3"></i>
        <span class="flex-1">${message}</span>
        <button onclick="this.parentElement.remove()" class="ml-3 text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
        </button>
      `;

      const className = `flex items-center p-4 mb-2 border rounded-lg shadow-lg transform transition-all duration-300 ease-in-out translate-x-full opacity-0 ${colors}`;

      const toast = toastUtils.createToast(content, className);
      toastUtils.showToast(toast, container);
    },

    showConnectionToast(message, type = "info") {
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

      setTimeout(() => {
        toast.classList.remove("translate-x-full", "opacity-0");
      }, 10);

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

      setTimeout(() => {
        toast.classList.remove("translate-x-full", "opacity-0");
        const progressBar = toast.querySelector(".absolute.bottom-0");
        if (progressBar) {
          setTimeout(() => {
            progressBar.style.width = "0%";
          }, 100);
        }
      }, 10);

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

    showProgressToast(message, progress = 0, fileSize = null) {
      const container = document.getElementById("toast-container");
      const toast = document.createElement("div");
      const toastId = `progress-toast-${Date.now()}`;

      toast.id = toastId;
      toast.className = `progress-toast relative p-4 mb-3 border rounded-lg shadow-xl bg-gradient-to-r from-blue-50 to-blue-100 border-blue-300 text-blue-900 transform transition-all duration-500 ease-in-out translate-x-full opacity-0 scale-95 w-[400px]`;

      const fileSizeInfo = fileSize ? `File size: ${fileSize}` : "";

      toast.innerHTML = `
        <div class="flex items-center mb-3">
          <div class="text-xl mr-3 animate-bounce-gentle">📦</div>
          <div class="flex-1">
            <div class="font-bold text-sm transition-all duration-300">${message}</div>
            <div class="text-xs opacity-75 mt-1 flex items-center justify-between">
              <span class="progress-text transition-all duration-300">${progress}% complete</span>
              <span class="ml-2 text-gray-500 eta-text"></span>
            </div>
            <div class="text-xs opacity-60 mt-1 step-timing-info"></div>
          </div>
          <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-gray-400 hover:text-gray-600 transition-colors">
            <i class="fas fa-times text-xs"></i>
          </button>
        </div>
        <div class="w-full bg-blue-200 rounded-full h-3 mb-2 overflow-hidden">
          <div class="progress-bar bg-gradient-to-r from-blue-400 to-blue-600 h-3 rounded-full transition-all duration-700 ease-out progress-bar-animated" style="width: ${progress}%"></div>
        </div>
        <div class="text-xs opacity-60">
          <span class="file-size-info">${fileSizeInfo}</span>
          <span class="ml-2 speed-info"></span>
        </div>
      `;

      container.appendChild(toast);

      setTimeout(() => {
        toast.classList.remove("translate-x-full", "opacity-0", "scale-95");
        toast.classList.add("scale-100");
      }, 10);

      toast.dataset.startTime = Date.now();

      return toastId;
    },

    updateProgressToast(toastId, message, progress, additionalInfo = null) {
      const toast = document.getElementById(toastId);
      if (!toast) return;

      const startTime = parseInt(toast.dataset.startTime);
      const currentTime = Date.now();
      const elapsedTime = currentTime - startTime;

      if (!toast.dataset.lastUpdateTime) {
        toast.dataset.lastUpdateTime = currentTime;
        toast.dataset.lastMessage = message;
        toast.dataset.updateCount = 0;
      }

      const lastUpdateTime = parseInt(toast.dataset.lastUpdateTime);
      const lastMessage = toast.dataset.lastMessage;
      const updateCount = parseInt(toast.dataset.updateCount);

      const MIN_DISPLAY_TIME = 800;
      const timeSinceLastUpdate = currentTime - lastUpdateTime;

      if (message !== lastMessage && timeSinceLastUpdate < MIN_DISPLAY_TIME) {
        toast.dataset.pendingMessage = message;
        toast.dataset.pendingProgress = progress;
        toast.dataset.pendingAdditionalInfo = additionalInfo || "";

        setTimeout(() => {
          const pendingMessage = toast.dataset.pendingMessage;
          const pendingProgress = toast.dataset.pendingProgress;
          const pendingAdditionalInfo = toast.dataset.pendingAdditionalInfo;

          if (pendingMessage) {
            this.updateProgressToast(
              toastId,
              pendingMessage,
              parseInt(pendingProgress),
              pendingAdditionalInfo
            );
            delete toast.dataset.pendingMessage;
            delete toast.dataset.pendingProgress;
            delete toast.dataset.pendingAdditionalInfo;
          }
        }, MIN_DISPLAY_TIME - timeSinceLastUpdate);

        return;
      }

      toast.dataset.lastUpdateTime = currentTime;
      toast.dataset.lastMessage = message;
      toast.dataset.updateCount = updateCount + 1;

      const messageElement = toast.querySelector(".font-bold");
      if (messageElement && messageElement.textContent !== message) {
        messageElement.style.opacity = "0.5";
        setTimeout(() => {
          messageElement.textContent = message;
          messageElement.style.opacity = "1";
        }, 150);
      }

      let etaText = "";
      if (progress > 0 && progress < 100 && elapsedTime > 1000) {
        const progressRate = progress / (elapsedTime / 1000);
        const remainingProgress = 100 - progress;
        const etaSeconds = remainingProgress / progressRate;

        if (etaSeconds < 60) {
          etaText = `~${Math.round(etaSeconds)}s remaining`;
        } else {
          etaText = `~${Math.round(etaSeconds / 60)}m remaining`;
        }
      }

      const progressText = toast.querySelector(".progress-text");
      if (progressText) {
        const oldProgress = parseInt(progressText.textContent);
        const newProgress = progress;

        if (Math.abs(newProgress - oldProgress) > 5) {
          this.animateProgressNumber(progressText, oldProgress, newProgress);
        } else {
          progressText.textContent = `${progress}% complete`;
        }
      }

      const etaElement = toast.querySelector(".eta-text");
      if (etaElement) {
        etaElement.textContent = etaText;
      }

      if (additionalInfo) {
        const fileSizeInfo = toast.querySelector(".file-size-info");
        if (fileSizeInfo) {
          fileSizeInfo.textContent = additionalInfo;
        }
      }

      const progressBar = toast.querySelector(".progress-bar");
      if (progressBar) {
        if (progress > 0 && progress < 100) {
          progressBar.classList.add("progress-bar-animated");
        }

        progressBar.style.width = `${Math.max(0, progress)}%`;

        if (progress >= 100) {
          progressBar.className =
            "progress-bar bg-gradient-to-r from-green-400 to-green-600 h-3 rounded-full transition-all duration-700 ease-out";
          toast.className = toast.className.replace(
            "from-blue-50 to-blue-100 border-blue-300 text-blue-900",
            "from-green-50 to-green-100 border-green-300 text-green-900"
          );

          this.addSparkleEffect(toast);
        } else if (progress < 0) {
          progressBar.className =
            "progress-bar bg-gradient-to-r from-red-400 to-red-600 h-3 rounded-full transition-all duration-700 ease-out";
          toast.className = toast.className.replace(
            "from-blue-50 to-blue-100 border-blue-300 text-blue-900",
            "from-red-50 to-red-100 border-red-300 text-red-900"
          );
          progressBar.style.width = "100%";

          toast.classList.add("animate-shake");
          setTimeout(() => toast.classList.remove("animate-shake"), 500);
        } else if (progress >= 80) {
          progressBar.className =
            "progress-bar bg-gradient-to-r from-green-300 to-blue-500 h-3 rounded-full transition-all duration-700 ease-out progress-bar-animated";
        }
      }

      const icon = toast.querySelector(".text-xl");
      if (icon) {
        if (progress >= 100) {
          icon.textContent = "✅";
          icon.classList.remove("animate-bounce-gentle");
          icon.classList.add("animate-pulse");
        } else if (progress < 0) {
          icon.textContent = "❌";
          icon.classList.remove("animate-bounce-gentle");
          icon.classList.add("animate-pulse");
        } else if (progress > 0) {
          icon.textContent = "🚀";
          if (!icon.classList.contains("animate-bounce-gentle")) {
            icon.classList.add("animate-bounce-gentle");
          }
        }
      }
    },

    animateProgressNumber(element, start, end) {
      const duration = 500;
      const startTime = Date.now();

      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);

        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (end - start) * easeOut);

        element.textContent = `${current}% complete`;

        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };

      animate();
    },

    addSparkleEffect(toast) {
      const sparkles = ["✨", "⭐", "🌟", "💫"];
      const sparkleContainer = document.createElement("div");
      sparkleContainer.className =
        "absolute inset-0 pointer-events-none overflow-hidden";

      for (let i = 0; i < 6; i++) {
        const sparkle = document.createElement("div");
        sparkle.textContent =
          sparkles[Math.floor(Math.random() * sparkles.length)];
        sparkle.className = "absolute text-yellow-400 text-xs animate-ping";
        sparkle.style.left = Math.random() * 100 + "%";
        sparkle.style.top = Math.random() * 100 + "%";
        sparkle.style.animationDelay = i * 100 + "ms";
        sparkleContainer.appendChild(sparkle);

        setTimeout(() => sparkle.remove(), 1000);
      }

      toast.style.position = "relative";
      toast.appendChild(sparkleContainer);
      setTimeout(() => sparkleContainer.remove(), 1200);
    },

    hideProgressToast(toastId) {
      const toast = document.getElementById(toastId);
      if (!toast) return;

      const progressBar = toast.querySelector(".progress-bar");
      const isSuccess =
        progressBar && progressBar.classList.contains("from-green-400");

      if (isSuccess) {
        toast.classList.add("animate-bounce-gentle");

        toast.style.boxShadow = "0 0 30px rgba(34, 197, 94, 0.6)";

        setTimeout(() => {
          toast.style.boxShadow = "";
          toast.classList.remove("animate-bounce-gentle");
        }, 1000);
      }

      setTimeout(
        () => {
          toast.classList.add("translate-x-full", "opacity-0", "scale-95");
          setTimeout(() => {
            if (toast.parentElement) {
              toast.remove();
            }
          }, 500);
        },
        isSuccess ? 2000 : 1000
      );
    },

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

    forceReconnect() {
      this.showConnectionToast("Manually reconnecting...", "info");
      this.destroy();
      this.connectEventSource();
    },

    // Share link cache management methods
    clearShareLinkCache() {
      this.shareLinkCache.clear();
      this.showToast("Share link cache cleared", "info");
    },

    removeFromShareLinkCache(taskId) {
      this.shareLinkCache.delete(taskId);
    },

    getShareLinkFromCache(taskId) {
      return this.shareLinkCache.get(taskId);
    },

    getCacheSize() {
      return this.shareLinkCache.size;
    },
  };
}

document.addEventListener("DOMContentLoaded", function () {
  document.documentElement.style.scrollBehavior = "smooth";
});

document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") {
    const dashboardData = Alpine.store("dashboard");
    if (dashboardData && dashboardData.selectedTask) {
      dashboardData.selectedTask = null;
    }
  }
});

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

document.addEventListener("DOMContentLoaded", () => {
  const animatedElements = document.querySelectorAll(".task-card");
  animatedElements.forEach((el) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(20px)";
    el.style.transition = "opacity 0.6s ease, transform 0.6s ease";
    observer.observe(el);
  });
});

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
