// Template system for rendering HTML components
class Templates {
  static header(dashboard) {
    return `
            <header class="gradient-bg text-white shadow-2xl">
                <div class="container mx-auto px-6 py-8">
                    <div class="flex items-center justify-between flex-wrap w-full gap-3">
                        ${this.headerTitle()}
                        ${this.headerStats(dashboard)}
                    </div>
                </div>
            </header>
        `;
  }

  static headerTitle() {
    return `
            <div class="flex items-center space-x-4">
                <div class="bg-white bg-opacity-20 p-3 rounded-full">
                    <i class="fas fa-robot text-2xl"></i>
                </div>
                <div>
                    <h1 class="text-3xl font-bold">Prototype</h1>
                    <p class="text-blue-100">Task Dashboard</p>
                </div>
            </div>
        `;
  }

  static headerStats(dashboard) {
    return `
            <div class="flex items-center space-x-4 min-w-36">
                <div class="bg-white bg-opacity-20 px-4 py-2 rounded-full">
                    <span class="text-sm">Total Tasks: <span x-text="tasks.length" class="font-bold"></span></span>
                </div>
                ${this.connectionStatus()}
                ${this.refreshButton()}
            </div>
        `;
  }

  static connectionStatus() {
    return `
            <div class="bg-white bg-opacity-20 px-3 py-2 rounded-full flex items-center space-x-2">
                <div class="flex items-center space-x-1">
                    <div class="w-2 h-2 rounded-full" :class="{
                        'bg-green-400 animate-pulse': realtimeManager.connectionStatus === 'connected',
                        'bg-yellow-400 animate-ping': realtimeManager.connectionStatus === 'connecting',
                        'bg-red-400': realtimeManager.connectionStatus === 'disconnected'
                    }"></div>
                    <span class="text-xs">
                        <span x-show="realtimeManager.connectionStatus === 'connected'">Live</span>
                        <span x-show="realtimeManager.connectionStatus === 'connecting'">Connecting</span>
                        <span x-show="realtimeManager.connectionStatus === 'disconnected'">Offline</span>
                    </span>
                </div>
                <button @click="forceReconnect()" x-show="realtimeManager.connectionStatus === 'disconnected'"
                    class="text-xs hover:text-gray-200 transition-colors">
                    <i class="fas fa-redo"></i>
                </button>
            </div>
        `;
  }

  static refreshButton() {
    return `
            <button style="display: none;" @click="refreshTasks()"
                class="bg-white bg-opacity-20 hover:bg-opacity-30 px-4 py-2 rounded-full transition-all duration-300 transform hover:scale-105">
                <i class="fas fa-sync-alt" :class="{ 'animate-spin': loading }"></i>
            </button>
        `;
  }

  static statsCards() {
    return `
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                ${this.statCard(
                  "fas fa-tasks",
                  "blue",
                  "Total Tasks",
                  "tasks.length"
                )}
                ${this.statCard(
                  "fas fa-check-circle",
                  "green",
                  "Completed",
                  "completedTasks"
                )}
                ${this.statCard(
                  "fas fa-clock",
                  "yellow",
                  "In Progress",
                  "inProgressTasks"
                )}
                ${this.statCard(
                  "fas fa-exclamation-triangle",
                  "red",
                  "Failed",
                  "failedTasks"
                )}
            </div>
        `;
  }

  static statCard(icon, color, label, value) {
    return `
            <div class="bg-white rounded-2xl shadow-lg p-6 transform hover:scale-105 transition-all duration-300">
                <div class="flex items-center">
                    <div class="bg-${color}-100 rounded-full w-12 h-12 grid place-items-center">
                        <i class="${icon} text-${color}-600"></i>
                    </div>
                    <div class="ml-4 flex-1">
                        <p class="text-gray-600 text-sm">${label}</p>
                        <p class="text-2xl font-bold text-gray-800" x-text="${value}"></p>
                    </div>
                </div>
            </div>
        `;
  }

  static taskList() {
    return `
            <div class="bg-white rounded-2xl shadow-xl overflow-hidden">
                ${this.taskListHeader()}
                ${this.taskListContent()}
            </div>
        `;
  }

  static taskListHeader() {
    return `
            <div class="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6 w-full">
                <h2 class="text-2xl font-bold flex items-center">
                    <i class="fas fa-list mr-3"></i> Recent Tasks
                </h2>
            </div>
        `;
  }

  static taskListContent() {
    return `
            <div class="p-6">
                <template x-if="tasks.length === 0">
                    ${this.emptyState()}
                </template>

                <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                    <template x-for="task in tasks" :key="task.id">
                        ${this.taskCard()}
                    </template>
                </div>
            </div>
        `;
  }

  static emptyState() {
    return `
            <div class="text-center py-12">
                <div class="text-gray-400 text-6xl mb-4">
                    <i class="fas fa-inbox"></i>
                </div>
                <p class="text-gray-600 text-lg">No tasks found</p>
                <p class="text-gray-400">Create your first task to get started</p>
            </div>
        `;
  }

  static taskCard() {
    return `
            <div class="task-card bg-white border border-gray-200 rounded-xl shadow-lg p-6 transition-all duration-300 cursor-pointer animate-fade-in"
                @click="selectTask(task)">
                ${this.taskHeader()}
                ${this.taskProgress()}
                ${this.taskDetails()}
                ${this.taskFeatures()}
            </div>
        `;
  }

  static taskHeader() {
    return `
            <div class="flex items-start justify-between mb-4">
                <div class="flex-1">
                    <h3 class="text-lg font-bold text-gray-800 mb-1" x-text="task.title"></h3>
                    <p class="text-sm text-gray-500" x-text="formatDate(task.created_at)"></p>
                </div>
                <div class="flex items-center space-x-2">
                    <span class="status-badge px-3 py-1 rounded-full text-xs font-medium"
                        :class="getStatusColor(task.status)" x-text="task.status"></span>
                    <template x-if="task.status === 'completed'">
                        ${this.shareButton()}
                    </template>
                </div>
            </div>
        `;
  }

  static shareButton() {
    return `
            <div class="flex items-center space-x-1">
                <button @click.stop="uploadTaskFiles(task.id)"
                    :disabled="isTaskLoadingShare(task.id)"
                    class="text-green-600 hover:text-green-800 transition-colors bg-green-50 hover:bg-green-100 px-2 py-1 rounded text-xs disabled:opacity-50 disabled:cursor-not-allowed">
                    <i class="mr-1" :class="isTaskLoadingShare(task.id) ? 'fa-solid fa-circle-notch animate-spin' : 'fas fa-share'"></i>Share
                </button>
            </div>
        `;
  }

  static taskProgress() {
    return `
            <div class="mb-4">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-sm font-medium text-gray-700">Progress</span>
                    <span class="text-sm text-gray-500" x-text="task.progress + '%'"></span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div class="progress-bar h-2 rounded-full transition-all duration-500 ease-out"
                        :class="[getProgressColor(task.status), { 'active': task.status !== 'completed' && task.status !== 'failed' }]"
                        :style="\`width: \${task.progress}%\`"></div>
                </div>
            </div>
        `;
  }

  static taskDetails() {
    return `
            <template x-if="task.status !== 'completed' && task.status !== 'failed' && task.current_step">
                <div class="mb-3">
                    <p class="text-sm text-gray-600">
                        <i class="fas fa-cog animate-spin mr-1"></i>
                        <span x-text="task.current_step"></span>
                    </p>
                </div>
            </template>

            <template x-if="task.total_steps > 0">
                <div class="flex items-center text-sm text-gray-500 mb-3">
                    <i class="fas fa-list-ol mr-2"></i>
                    <span x-text="\`\${task.completed_steps}/\${task.total_steps} steps\`"></span>
                </div>
            </template>
        `;
  }

  static taskFeatures() {
    return `
            <div class="flex items-center text-sm gap-x-4">
                <template x-if="task.has_index_html">
                    <span class="flex items-center text-green-600">
                        <i class="fas fa-globe mr-1"></i>
                        Website
                    </span>
                </template>
                <template x-if="task.output_directory">
                    <span class="flex items-center text-blue-600">
                        <i class="fas fa-folder mr-1"></i>
                        Files
                    </span>
                </template>
            </div>
        `;
  }

  static modal() {
    return `
            <div x-show="selectedTask" x-transition:enter="transition ease-out duration-300"
                x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100"
                x-transition:leave="transition ease-in duration-200" x-transition:leave-start="opacity-100"
                x-transition:leave-end="opacity-0"
                class="fixed inset-0 bg-black bg-opacity-80 flex flex-col items-center justify-center p-4 z-50"
                @click.self="closeTaskModal()">
                
                ${this.modalContent()}
            </div>
        `;
  }

  static modalContent() {
    return `
            <div class="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden"
                x-show="selectedTask" x-transition:enter="transition ease-out duration-300"
                x-transition:enter-start="opacity-0 transform scale-95"
                x-transition:enter-end="opacity-100 transform scale-100"
                x-transition:leave="transition ease-in duration-200"
                x-transition:leave-start="opacity-100 transform scale-100"
                x-transition:leave-end="opacity-0 transform scale-95">
                
                ${this.modalHeader()}
                ${this.modalBody()}
            </div>
        `;
  }

  static modalHeader() {
    return `
            <div class="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-3 w-full">
                <div class="flex items-center justify-between">
                    <div>
                        <h2 class="text-xl font-bold" x-text="selectedTask?.title"></h2>
                    </div>
                    <div class="flex items-center space-x-3">
                        <template x-if="selectedTask?.status === 'completed'">
                            <div class="flex items-center space-x-3">
                                <div class="flex items-center">
                                    <button x-show="showHTMLFile !== ''" @click="toggleDetailView()"
                                        :title="viewTaskSteps ? 'Show Preview' : 'Show Steps'"
                                        aria-label="Toggle preview / steps"
                                        class="ml-2 bg-opacity-20 hover:bg-opacity-30 rounded-full transition-colors flex items-center">
                                        <i :class="!viewTaskSteps ? 'fas fa-info-circle text-white scale-110' : 'fas fa-list text-white scale-110'"
                                            class="text-lg"></i>
                                    </button>
                                </div>
                                <span class="tooltip-container tooltip-bottom" tabindex="0" aria-label="Deploy and share">
                                    <button @click="uploadTaskFiles(selectedTask.id)"
                                        :disabled="isTaskLoadingShare(selectedTask?.id)"
                                        class="px-4 py-3 rounded-lg transition-all flex items-center disabled:opacity-50 disabled:cursor-not-allowed">
                                        <i :class="isTaskLoadingShare(selectedTask?.id) ? 'fa-solid fa-circle-notch animate-spin scale-110' : 'fa-solid fa-share scale-110'"></i>
                                    </button>
                                    <span class="tooltip-box">
                                        <span class="text-black">Deploy and share</span>
                                        <span class="tooltip-arrow" aria-hidden="true"></span>
                                    </span>
                                </span>
                            </div>
                        </template>
                        <button @click="closeTaskModal()"
                            class="bg-white bg-opacity-20 hover:bg-opacity-30 p-2 rounded-lg transition-all w-10">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
  }

  static modalBody() {
    return `
            <div class="overflow-y-hidden bg-white w-full h-[90vh]">
                ${this.modalPreview()}
                ${this.modalDetails()}
            </div>
        `;
  }

  static modalPreview() {
    return `
            <div x-show="!viewTaskSteps" class="h-full">
                <template x-if="selectedTask?.status === 'completed' && showHTMLFile !== ''">
                    <div class="h-full">
                        <iframe :src="\`./api/tasks/\${selectedTask.id}/preview/\${showHTMLFile}\`"
                            class="w-full h-full border-0"></iframe>
                    </div>
                </template>
            </div>
        `;
  }

  static modalDetails() {
    return `
            <div class="p-6 h-full overflow-y-auto">
                ${this.progressSection()}
                <div x-show="viewTaskSteps">
                    ${this.fileListSection()}
                    ${this.taskStepsSection()}
                    ${this.taskInfoSection()}
                    ${this.errorSection()}
                </div>
            </div>
        `;
  }

  static progressSection() {
    return `
            <template x-if="selectedTask?.status !== 'completed'">
                <div class="mb-6">
                    <h3 class="text-lg text-black font-bold mb-4 flex items-center">
                        <i class="fas fa-tasks mr-2 text-blue-600"></i>
                        Progress
                    </h3>
                    <div class="bg-gray-50 rounded-lg p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="font-medium">Overall Progress</span>
                            <span class="text-lg font-bold" x-text="selectedTask?.progress + '%'"></span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-3 mb-4">
                            <div class="progress-bar h-3 rounded-full transition-all duration-500"
                                :class="[getProgressColor(selectedTask?.status), { 'active': selectedTask?.status !== 'completed' && selectedTask?.status !== 'failed' }]"
                                :style="\`width: \${selectedTask?.progress}%\`"></div>
                        </div>
                        <template x-if="selectedTask?.current_step">
                            <div class="flex items-center text-sm text-gray-600">
                                <i class="fas fa-cog animate-spin mr-2"></i>
                                <span x-text="selectedTask?.current_step"></span>
                            </div>
                        </template>
                    </div>
                </div>
            </template>
        `;
  }

  static fileListSection() {
    return `
            <div class="mb-6" x-show="taskFiles.length > 0">
                <h3 class="text-lg font-bold mb-4 flex items-center">
                    <i class="fas fa-folder-open mr-2 text-yellow-600"></i> Generated Files
                </h3>
                <div class="bg-gray-50 rounded-lg p-4" x-data="folderTree">
                    <template x-for="item in getAllItems(taskFiles)" :key="item.data.path || item.data.name">
                        <div :style="\`margin-left: \${item.depth * 20}px\`">
                            <template x-if="item.type === 'folder'">
                                <div class="flex items-center py-2 cursor-pointer hover:bg-gray-100 rounded px-2 mb-1" 
                                     @click="toggleFolder(item.data.path)">
                                    <i class="fas mr-2 text-yellow-600 transition-transform duration-200" 
                                       :class="isFolderCollapsed(item.data.path) ? 'fa-folder' : 'fa-folder-open'"></i>
                                    <i class="fas fa-chevron-right mr-2 text-gray-400 transition-transform duration-200 text-xs" 
                                       :class="{'rotate-90': !isFolderCollapsed(item.data.path)}"></i>
                                    <span class="font-medium text-gray-700" x-text="item.data.name"></span>
                                    <span class="ml-2 text-xs text-gray-500" x-text="\`(\${item.data.files.length + Object.keys(item.data.folders).length} items)\`"></span>
                                </div>
                            </template>
                            
                            <template x-if="item.type === 'file'">
                                <div class="flex items-center justify-between py-2 border-b border-gray-200 last:border-0 hover:bg-white rounded px-2 transition-colors">
                                    <div class="flex items-center">
                                        <i class="fas fa-file mr-2 text-gray-400" :class="{
                                            'fa-file-code text-blue-500': item.data.name.endsWith('.html') || item.data.name.endsWith('.css') || item.data.name.endsWith('.js'),
                                            'fa-file-image text-green-500': item.data.name.match(/\\.(jpg|jpeg|png|gif|svg)$/i),
                                            'fa-file-alt text-purple-500': item.data.name.endsWith('.md'),
                                            'fa-globe text-orange-500': item.data.is_index
                                        }"></i>
                                        <span x-text="item.data.name" class="font-medium"></span>
                                        <template x-if="showHTMLFile === item.data.path">
                                            <span class="ml-2 bg-orange-100 text-orange-800 text-xs px-2 py-1 rounded">Index</span>
                                        </template>
                                    </div>
                                    <div class="flex items-center space-x-2">
                                        <span class="text-sm text-gray-500" x-text="formatFileSize(item.data.size)"></span>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </template>
                </div>
            </div>
        `;
  }

  static taskStepsSection() {
    return `
            <div class="mb-6" x-show="taskSteps.length > 0">
                <h3 class="text-lg font-bold mb-4 flex items-center text-black">
                    <i class="fas fa-list-ol mr-2 text-purple-600"></i> Execution Steps
                </h3>
                <div class="bg-gray-50 rounded-lg p-4">
                    <template x-for="(step, index) in taskSteps" :key="step.id">
                        <div class="mb-4 p-4 border rounded-lg bg-white shadow-sm transition-all duration-300 hover:shadow-md"
                            :class="getStepStatusColor(step.status)">
                            <div class="flex items-start justify-between mb-2">
                                <div class="flex items-center space-x-3">
                                    <div class="text-lg" x-text="getStepTypeIcon(step.step_type)"></div>
                                    <div>
                                        <span class="font-medium" x-text="\`Step \${index + 1}\`"></span>
                                        <span class="text-sm text-gray-600 ml-2" x-text="step.step_type"></span>
                                    </div>
                                </div>
                                <div class="flex items-center space-x-2">
                                    <i :class="getStepStatusIcon(step.status)"></i>
                                    <span class="text-xs font-medium" x-text="step.status"></span>
                                </div>
                            </div>

                            <div class="text-sm mb-2">
                                <p class="text-gray-700" x-text="step.task_description"></p>
                            </div>

                            <template x-if="step.expectation">
                                <div class="text-xs text-gray-500 mb-2">
                                    <strong>Expected:</strong> <span x-text="step.expectation"></span>
                                </div>
                            </template>

                            <template x-if="step.output && step.status === 'completed'">
                                <div class="mt-2 p-2 bg-gray-100 rounded text-xs">
                                    <strong>Output:</strong>
                                    <pre class="mt-1 whitespace-pre-wrap" x-text="step.output"></pre>
                                </div>
                            </template>
                        </div>
                    </template>
                </div>
            </div>
        `;
  }

  static taskInfoSection() {
    return `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="bg-gray-50 rounded-lg p-4">
                    <h4 class="font-bold mb-2">Task Details</h4>
                    <div class="space-y-2 text-sm">
                        <div><strong>Status:</strong> <span x-text="selectedTask?.status"></span></div>
                        <div><strong>Created:</strong> <span x-text="formatDate(selectedTask?.created_at)"></span></div>
                        <div><strong>Progress:</strong> <span x-text="selectedTask?.progress + '%'"></span></div>
                        <template x-if="selectedTask?.total_steps > 0">
                            <div><strong>Steps:</strong> <span x-text="\`\${selectedTask?.completed_steps}/\${selectedTask?.total_steps}\`"></span></div>
                        </template>
                    </div>
                </div>

                <template x-if="selectedTask?.expectation">
                    <div class="bg-gray-50 rounded-lg p-4">
                        <h4 class="font-bold mb-2">Requirements</h4>
                        <p class="text-sm text-gray-700" x-text="selectedTask?.expectation"></p>
                    </div>
                </template>
            </div>
        `;
  }

  static errorSection() {
    return `
            <template x-if="selectedTask?.error_message">
                <div class="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
                    <h4 class="font-bold text-red-800 mb-2">Error Details</h4>
                    <p class="text-sm text-red-700" x-text="selectedTask?.error_message"></p>
                </div>
            </template>
        `;
  }
}

// Export for global use
if (typeof window !== "undefined") {
  window.Templates = Templates;
}
