// Folder tree component for file management
class FolderTreeManager {
  constructor() {
    this.collapsedFolders = {};
  }

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
            folders: {},
            files: [],
            name: part,
            path: currentPath,
          };
        }
        current = current.folders[part];
      });

      current.files.push({ ...file, name: fileName });
    });

    return tree;
  }

  toggleFolder(folderPath) {
    // If folder path doesn't exist, it means it's collapsed by default, so we expand it
    if (this.collapsedFolders[folderPath] === undefined) {
      this.collapsedFolders[folderPath] = false; // expanded
    } else {
      this.collapsedFolders[folderPath] = !this.collapsedFolders[folderPath];
    }
  }

  isFolderCollapsed(folderPath) {
    // Return true (collapsed) by default if folder state is not set
    return this.collapsedFolders[folderPath] !== false;
  }

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
        items = items.concat(this.renderTree(folder, depth + 1));
      }
    });

    return items;
  }

  getAllItems(taskFiles) {
    return this.renderTree(this.buildFolderTree(taskFiles));
  }

  getFileIcon(fileName) {
    const extension = fileName.toLowerCase().split(".").pop();

    const iconMap = {
      html: "fa-file-code text-blue-500",
      css: "fa-file-code text-blue-500",
      js: "fa-file-code text-blue-500",
      ts: "fa-file-code text-blue-500",
      json: "fa-file-code text-purple-500",
      md: "fa-file-alt text-purple-500",
      txt: "fa-file-alt text-gray-500",
      jpg: "fa-file-image text-green-500",
      jpeg: "fa-file-image text-green-500",
      png: "fa-file-image text-green-500",
      gif: "fa-file-image text-green-500",
      svg: "fa-file-image text-green-500",
      pdf: "fa-file-pdf text-red-500",
      zip: "fa-file-archive text-yellow-500",
      rar: "fa-file-archive text-yellow-500",
    };

    return iconMap[extension] || "fa-file text-gray-400";
  }

  reset() {
    this.collapsedFolders = {};
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.FolderTreeManager = FolderTreeManager;
}
