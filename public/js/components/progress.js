// Progress management system
class ProgressManager {
  constructor(toastManager) {
    this.toastManager = toastManager;
    this.activeProgress = new Map();
  }

  showProgressToast(message, progress = 0, fileSize = null) {
    const container = DomUtils.getContainer("toast-container");
    const toast = DomUtils.createElement("div");
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
      toast.style.opacity = "1";
      toast.style.transform = "translateX(0) scale(1)";
    }, 10);

    toast.dataset.startTime = Date.now();

    // Store progress info
    this.activeProgress.set(toastId, {
      startTime: Date.now(),
      lastUpdateTime: Date.now(),
      lastMessage: message,
      updateCount: 0,
    });

    return toastId;
  }

  updateProgressToast(toastId, message, progress, additionalInfo = null) {
    const toast = document.getElementById(toastId);
    if (!toast) return;

    const progressInfo = this.activeProgress.get(toastId);
    if (!progressInfo) return;

    const currentTime = Date.now();
    const elapsedTime = currentTime - progressInfo.startTime;

    const MIN_DISPLAY_TIME = 800;
    const timeSinceLastUpdate = currentTime - progressInfo.lastUpdateTime;

    if (
      message !== progressInfo.lastMessage &&
      timeSinceLastUpdate < MIN_DISPLAY_TIME
    ) {
      setTimeout(
        () =>
          this.updateProgressToast(toastId, message, progress, additionalInfo),
        MIN_DISPLAY_TIME - timeSinceLastUpdate
      );
      return;
    }

    // Update progress info
    progressInfo.lastUpdateTime = currentTime;
    progressInfo.lastMessage = message;
    progressInfo.updateCount++;

    const messageElement = toast.querySelector(".font-bold");
    if (messageElement && messageElement.textContent !== message) {
      messageElement.style.opacity = "0.5";
      setTimeout(() => {
        messageElement.textContent = message;
        messageElement.style.opacity = "1";
      }, 200);
    }

    let etaText = "";
    let speedText = "";
    if (progress > 0 && progress < 100 && elapsedTime > 1000) {
      const estimatedTotal = (elapsedTime / progress) * 100;
      const remainingTime = estimatedTotal - elapsedTime;
      if (remainingTime > 0) {
        const remainingSeconds = Math.ceil(remainingTime / 1000);
        etaText = `~${remainingSeconds}s left`;
      }
    }

    const progressText = toast.querySelector(".progress-text");
    if (progressText) {
      this.animateProgressNumber(
        progressText,
        parseInt(progressText.textContent),
        progress
      );
    }

    const etaElement = toast.querySelector(".eta-text");
    if (etaElement) {
      etaElement.textContent = etaText;
    }

    const speedElement = toast.querySelector(".speed-info");
    if (speedElement) {
      speedElement.textContent = speedText;
    }

    if (additionalInfo) {
      const stepTimingElement = toast.querySelector(".step-timing-info");
      if (stepTimingElement) {
        stepTimingElement.textContent = additionalInfo;
      }
    }

    const progressBar = toast.querySelector(".progress-bar");
    if (progressBar) {
      progressBar.style.width = `${progress}%`;

      if (progress >= 100) {
        progressBar.className = progressBar.className.replace(
          "from-blue-400 to-blue-600",
          "from-green-400 to-green-600"
        );
        this.addSparkleEffect(toast);
      }
    }

    const icon = toast.querySelector(".text-xl");
    if (icon && progress >= 100) {
      icon.textContent = "✅";
    }
  }

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
  }

  addSparkleEffect(toast) {
    const sparkles = ["✨", "⭐", "🌟", "💫"];
    const sparkleContainer = DomUtils.createElement("div");
    sparkleContainer.className =
      "absolute inset-0 pointer-events-none overflow-hidden";

    for (let i = 0; i < 6; i++) {
      setTimeout(() => {
        const sparkle = DomUtils.createElement("div");
        sparkle.textContent =
          sparkles[Math.floor(Math.random() * sparkles.length)];
        sparkle.className = "absolute text-lg animate-ping";
        sparkle.style.left = Math.random() * 80 + 10 + "%";
        sparkle.style.top = Math.random() * 60 + 20 + "%";
        sparkle.style.animationDelay = Math.random() * 0.5 + "s";

        sparkleContainer.appendChild(sparkle);

        setTimeout(() => sparkle.remove(), 1000);
      }, i * 200);
    }

    toast.style.position = "relative";
    toast.appendChild(sparkleContainer);
    setTimeout(() => sparkleContainer.remove(), 1200);
  }

  hideProgressToast(toastId) {
    const toast = document.getElementById(toastId);
    if (!toast) return;

    const progressBar = toast.querySelector(".progress-bar");
    const isSuccess =
      progressBar && progressBar.classList.contains("from-green-400");

    if (isSuccess) {
      setTimeout(() => {
        this.toastManager.animateOut(toast);
      }, 2000);
    } else {
      setTimeout(() => {
        this.toastManager.animateOut(toast);
      }, 1000);
    }

    // Clean up progress info
    this.activeProgress.delete(toastId);
  }

  start(message, initialProgress = 0, fileSize = null) {
    return this.showProgressToast(message, initialProgress, fileSize);
  }

  update(toastId, message, progress, additionalInfo = null) {
    this.updateProgressToast(toastId, message, progress, additionalInfo);
  }

  complete(toastId, finalMessage = "Complete!") {
    this.updateProgressToast(toastId, finalMessage, 100);
    setTimeout(() => this.hideProgressToast(toastId), 2000);
  }

  fail(toastId, errorMessage = "Failed") {
    const toast = document.getElementById(toastId);
    if (!toast) return;

    const progressBar = toast.querySelector(".progress-bar");
    if (progressBar) {
      progressBar.className = progressBar.className.replace(
        "from-blue-400 to-blue-600",
        "from-red-400 to-red-600"
      );
    }

    const icon = toast.querySelector(".text-xl");
    if (icon) {
      icon.textContent = "❌";
    }

    const messageElement = toast.querySelector(".font-bold");
    if (messageElement) {
      messageElement.textContent = errorMessage;
    }

    setTimeout(() => this.hideProgressToast(toastId), 3000);
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.ProgressManager = ProgressManager;
}
