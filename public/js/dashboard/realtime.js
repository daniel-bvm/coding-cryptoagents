// Real-time connection management
class RealtimeManager {
  constructor(dashboard) {
    this.dashboard = dashboard;
    this.eventSource = null;
    this.connectionStatus = "disconnected";
    this.reconnectAttempts = 0;
    this.reconnectTimeout = null;
  }

  connect() {
    if (this.eventSource) {
      this.eventSource.close();
    }

    this.connectionStatus = "connecting";
    this.dashboard.toastManager.showConnectionToast(
      "Connecting to real-time updates...",
      "info"
    );

    this.eventSource = new EventSource("./api/subscribe?channels=tasks");

    this.eventSource.onopen = () => {
      this.connectionStatus = "connected";
      this.reconnectAttempts = 0;
      this.dashboard.toastManager.showConnectionToast(
        "Connected to real-time updates",
        "success"
      );
    };

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleRealtimeUpdate(data);
      } catch (error) {
        console.error("Error parsing real-time data:", error);
      }
    };

    this.eventSource.onerror = (error) => {
      this.connectionStatus = "disconnected";
      this.eventSource.close();

      this.reconnectAttempts = (this.reconnectAttempts || 0) + 1;
      const delay = 2000;

      this.dashboard.toastManager.showConnectionToast(
        `Connection lost. Reconnecting in 2s (attempt ${this.reconnectAttempts})`,
        "warning"
      );

      this.reconnectTimeout = setTimeout(() => {
        this.connect();
      }, delay);
    };
  }

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
        this.dashboard.taskManager.addTask(task);
        break;

      case "task_updated":
      case "task_progress":
      case "task_status":
      case "task_output":
        if (task) {
          this.dashboard.taskManager.updateTask(task);
        }
        break;

      case "task_deleted":
        this.dashboard.taskManager.removeTask(task_id);
        break;

      case "plan_step_created":
        if (step && step_number && title) {
          this.dashboard.showPlanStepNotification(step, step_number, title);
        }
        break;

      case "plan_completed":
        if (title && total_steps && plan_summary) {
          this.dashboard.showPlanCompletedNotification(
            title,
            total_steps,
            plan_summary
          );
        }
        break;

      case "step_status_updated":
        this.dashboard.updateStepStatus(data.data);
        break;

      default:
        console.log("Unknown real-time event:", event_type);
    }
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this.connectionStatus = "disconnected";
  }

  forceReconnect() {
    this.dashboard.toastManager.showConnectionToast(
      "Manually reconnecting...",
      "info"
    );
    this.disconnect();
    this.connect();
  }

  getStatus() {
    return this.connectionStatus;
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.RealtimeManager = RealtimeManager;
}
