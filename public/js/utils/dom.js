// DOM utility functions
class DomUtils {
  static createElement(tag, className = "", innerHTML = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (innerHTML) element.innerHTML = innerHTML;
    return element;
  }

  static fadeIn(element, duration = 300) {
    element.style.opacity = "0";
    element.style.transform = "translateX(100%)";
    element.style.transition = `opacity ${duration}ms ease, transform ${duration}ms ease`;

    setTimeout(() => {
      element.style.opacity = "1";
      element.style.transform = "translateX(0)";
    }, 10);
  }

  static fadeOut(element, duration = 300) {
    element.style.transition = `opacity ${duration}ms ease, transform ${duration}ms ease`;
    element.style.opacity = "0";
    element.style.transform = "translateX(100%)";

    setTimeout(() => {
      if (element.parentNode) {
        element.parentNode.removeChild(element);
      }
    }, duration);
  }

  static animateScale(element, scale = 0.95, duration = 150) {
    element.style.transform = `scale(${scale})`;
    setTimeout(() => {
      element.style.transform = "";
    }, duration);
  }

  static getContainer(id) {
    return document.getElementById(id) || document.body;
  }

  static copyToClipboard(text) {
    return navigator.clipboard.writeText(text);
  }

  static setupIntersectionObserver(selector, options = {}) {
    const defaultOptions = {
      threshold: 0.1,
      rootMargin: "0px 0px -50px 0px",
    };

    const observerOptions = { ...defaultOptions, ...options };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.style.opacity = "1";
          entry.target.style.transform = "translateY(0)";
        }
      });
    }, observerOptions);

    document.querySelectorAll(selector).forEach((el) => {
      el.style.opacity = "0";
      el.style.transform = "translateY(20px)";
      el.style.transition = "opacity 0.6s ease, transform 0.6s ease";
      observer.observe(el);
    });

    return observer;
  }

  static setupButtonAnimation() {
    document.addEventListener("click", function (e) {
      if (e.target.matches("button") || e.target.closest("button")) {
        const button = e.target.matches("button")
          ? e.target
          : e.target.closest("button");
        DomUtils.animateScale(button);
      }
    });
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.DomUtils = DomUtils;
}
