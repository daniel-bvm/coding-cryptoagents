// API client for server communication
class ApiClient {
  constructor() {
    this.baseUrl = window.location.origin;
  }

  async get(endpoint) {
    // Remove leading ./ if present and ensure proper URL construction
    const cleanEndpoint = endpoint.startsWith("./")
      ? endpoint.slice(2)
      : endpoint;
    const url = `${this.baseUrl}/${cleanEndpoint}`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  }

  async post(endpoint, data) {
    // Remove leading ./ if present and ensure proper URL construction
    const cleanEndpoint = endpoint.startsWith("./")
      ? endpoint.slice(2)
      : endpoint;
    const url = `${this.baseUrl}/${cleanEndpoint}`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  }

  async upload(endpoint, formData, onProgress = null) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      if (onProgress) {
        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            onProgress(percentComplete);
          }
        });
      }

      xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE) {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const response = JSON.parse(xhr.responseText);
              resolve(response);
            } catch (e) {
              resolve({ success: true });
            }
          } else {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      };

      // Remove leading ./ if present and ensure proper URL construction
      const cleanEndpoint = endpoint.startsWith("./")
        ? endpoint.slice(2)
        : endpoint;
      const url = `${this.baseUrl}/${cleanEndpoint}`;
      xhr.open("POST", url);
      xhr.send(formData);
    });
  }

  async getTasks() {
    return this.get("./api/tasks/");
  }

  async getTaskFiles(taskId) {
    return this.get(`./api/tasks/${taskId}/files`);
  }

  async getTaskSteps(taskId) {
    return this.get(`./api/tasks/${taskId}/steps`);
  }

  async downloadTask(taskId) {
    const response = await fetch(`./api/tasks/${taskId}/download`);
    if (!response.ok) {
      throw new Error(`Download failed with status ${response.status}`);
    }
    return response.blob();
  }

  async checkCdnFile(url) {
    try {
      const response = await fetch(url);
      return response.ok;
    } catch (error) {
      return false;
    }
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.ApiClient = ApiClient;
}
