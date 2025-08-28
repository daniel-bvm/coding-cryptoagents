// Upload management system
class UploadManager {
  constructor(dashboard) {
    this.dashboard = dashboard;
    this.loadingShares = {};
    this.config = window.APP_CONFIG?.UPLOAD_CONFIG || {};
    this.api = new ApiClient();
    this.progressManager = new ProgressManager(dashboard.toastManager);
    this.taskManager = new TaskManager(dashboard);
  }

  async uploadTaskFiles(taskId) {
    try {
      this.loadingShares[taskId] = true;

      if (!this.dashboard.taskFiles || this.dashboard.taskFiles.length === 0) {
        console.log("Loading task files before upload...");
        await this.taskManager.loadTaskFiles(taskId);
      }

      if (!this.dashboard.taskFiles || this.dashboard.taskFiles.length === 0) {
        this.dashboard.toastManager.showToast("No files to upload", "error");
        return null;
      }
      console.log("file 1: ", this.dashboard.taskFiles);
      console.log("file 2: ", this.dashboard.selectedTask);

      const chosenFile = this.findBestHtmlFile();
      console.log(
        "🚀 ~ UploadManager ~ uploadTaskFiles ~ chosenFile:",
        chosenFile
      );

      const checkResponse = await fetch(
        `${window.APP_CONFIG.CDN_BASE_URL}/${taskId}/${chosenFile}`
      );
      if (checkResponse.ok) {
        return await this.handleExistingCdnLink(
          `${window.APP_CONFIG.CDN_BASE_URL}/${taskId}`
        );
      }

      return await this.uploadNewFiles(taskId);
    } catch (error) {
      this.dashboard.toastManager.showToast("Upload failed", "error");
      return null;
    } finally {
      delete this.loadingShares[taskId];
    }
  }

  async handleExistingCdnLink(existingUrl) {
    const chosenFile = this.findBestHtmlFile();

    if (!chosenFile) {
      this.dashboard.toastManager.showToast("No HTML file to share", "error");
      return null;
    }

    await this.copyShareLink(existingUrl, chosenFile);
    return existingUrl;
  }

  async createZipFromTaskFiles(taskId) {
    try {
      const blob = await this.api.downloadTask(taskId);
      return blob;
    } catch (error) {
      throw new Error("Failed to create deployment package");
    }
  }

  async uploadNewFiles(taskId) {
    let progressToastId = null;
    try {
      const startTime = Date.now();
      progressToastId = this.progressManager.start(
        "Preparing deployment...",
        0
      );
      await this.ensureMinimumStepTime(
        startTime,
        this.config.minimumStepTimes?.preparation || 500,
        progressToastId
      );

      const zipStartTime = Date.now();
      this.progressManager.update(
        progressToastId,
        "Creating deployment package...",
        5
      );
      const zipBlob = await this.createZipFromTaskFiles(taskId);
      if (!zipBlob) {
        throw new Error("Failed to create package");
      }
      await this.ensureMinimumStepTime(
        zipStartTime,
        this.config.minimumStepTimes?.zipCreation || 600,
        progressToastId
      );

      const fileSizeFormatted = Formatters.formatFileSize(zipBlob.size);

      const analysisStartTime = Date.now();
      this.progressManager.update(
        progressToastId,
        `Analyzing package (${fileSizeFormatted})...`,
        10
      );
      await this.ensureMinimumStepTime(
        analysisStartTime,
        this.config.minimumStepTimes?.analysis || 500,
        progressToastId
      );

      let uploadResult = await this.uploadFileWhole(
        taskId,
        zipBlob,
        progressToastId
      );

      if (!uploadResult) {
        throw new Error("Upload failed");
      }

      const chosenFile = this.findBestHtmlFile();
      if (!chosenFile) {
        throw new Error("No HTML file found");
      }

      const baseUrl =
        uploadResult.url || `${window.APP_CONFIG.CDN_BASE_URL}/${taskId}`;
      await this.copyShareLink(baseUrl, chosenFile);

      this.progressManager.complete(progressToastId, "Upload completed!");
      return baseUrl;
    } catch (error) {
      if (progressToastId) {
        this.progressManager.fail(progressToastId, error.message);
      }
      throw error;
    }
  }

  async uploadFileWhole(taskId, fileBlob, progressToastId) {
    const fileSizeFormatted = Formatters.formatFileSize(fileBlob.size);
    const startTime = Date.now();

    try {
      this.progressManager.update(
        progressToastId,
        `Preparing upload (${fileSizeFormatted})...`,
        15
      );
      await this.ensureMinimumStepTime(
        startTime,
        this.config.minimumStepTimes?.uploadPrep || 600,
        progressToastId
      );

      const uploadStartTime = Date.now();
      this.progressManager.update(
        progressToastId,
        `Uploading file (${fileSizeFormatted})...`,
        20
      );

      const formData = new FormData();
      formData.append("file", fileBlob, `${taskId}.zip`);

      // Use the API client for upload with progress tracking
      const result = await this.api.upload(
        `./api/tasks/${taskId}/upload`,
        formData,
        (progress) => {
          const adjustedProgress = 20 + progress * 0.6; // Scale from 20% to 80%
          this.progressManager.update(
            progressToastId,
            `Uploading... (${Math.round(progress)}%)`,
            adjustedProgress
          );
        }
      );

      this.progressManager.update(progressToastId, "Processing upload...", 90);
      await this.ensureMinimumStepTime(
        uploadStartTime,
        this.config.minimumStepTimes?.processing || 500,
        progressToastId
      );

      return result;
    } catch (error) {
      throw new Error(`Upload failed: ${error.message}`);
    }
  }

  async ensureMinimumStepTime(stepStartTime, minimumMs, toastId = null) {
    if (!this.config.enforceMinimumStepTiming) {
      return;
    }

    const elapsed = Date.now() - stepStartTime;
    if (elapsed < minimumMs) {
      const remaining = minimumMs - elapsed;
      await this.delay(remaining);
    }
  }

  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  findBestHtmlFile() {
    console.log(
      "🚀 ~ UploadManager ~ findBestHtmlFile ~ this.dashboard.taskFiles:",
      this.dashboard.taskFiles
    );
    if (
      !Array.isArray(this.dashboard.taskFiles) ||
      this.dashboard.taskFiles.length === 0
    ) {
      return null;
    }

    const indexFile = this.dashboard.taskFiles.find((f) =>
      f.path.toLowerCase().endsWith("index.html")
    );
    if (indexFile) {
      return indexFile.path;
    }

    const firstHTML = this.dashboard.taskFiles.find((f) =>
      f.path.toLowerCase().endsWith(".html")
    );

    return firstHTML ? firstHTML.path : null;
  }

  async copyShareLink(baseUrl, filePath) {
    const shareUrl = `${baseUrl}/${filePath}`;
    try {
      await DomUtils.copyToClipboard(shareUrl);
      this.dashboard.toastManager.showToast(
        "Share link copied to clipboard",
        "success"
      );
    } catch (err) {
      console.error("Failed to copy share link:", err);
      this.dashboard.toastManager.showToast(
        "Failed to copy share link",
        "error"
      );
    }
  }

  isTaskLoadingShare(taskId) {
    return !!this.loadingShares[taskId];
  }

  toggleMinimumStepTiming() {
    this.config.enforceMinimumStepTiming =
      !this.config.enforceMinimumStepTiming;
    this.dashboard.toastManager.showToast(
      `Minimum step timing ${
        this.config.enforceMinimumStepTiming ? "enabled" : "disabled"
      }`,
      "info"
    );
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.UploadManager = UploadManager;
}
