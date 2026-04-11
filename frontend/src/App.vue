<template>
  <CRTEffect :config="config">
    <div class="app-container">
      <HeaderBar
        :title="currentTitle"
        :currentTableIndex="currentTableIndex"
        :totalTables="totalTables"
        :showBackButton="currentView === 'table'"
        @prev="prevTable"
        @next="nextTable"
        @save="saveChanges"
        @back="showFileTree"
      />
      
      <div class="content-area">
        <div v-if="loading" class="status-screen">
          <div class="status-icon">▓</div>
          <div class="status-text blink">LOADING...</div>
        </div>
        
        <div v-else-if="error" class="status-screen error">
          <div class="status-icon">✕</div>
          <div class="status-text">{{ error }}</div>
        </div>
        
        <div v-else-if="allFilesData.length === 0" class="status-screen">
          <div class="status-icon">◇</div>
          <div class="status-text">NO .MD FILES FOUND</div>
          <div class="status-hint">Place markdown files in /data directory</div>
        </div>
        
        <!-- 文件树视图 -->
        <div v-else-if="currentView === 'file-tree'" class="file-tree-container">
          <FileTree
            :treeData="fileTree"
            :currentFile="currentFilePath"
            @file-select="selectFile"
            @toggle-directory="toggleDirectory"
            :openDirectories="openDirectories"
          />
        </div>
        
        <!-- 表格视图 -->
        <div v-else class="table-container">
          <TableView
            :key="`${currentFileIndex}-${currentTableIndex}`"
            :tableData="currentTableData"
            @update="handleTableUpdate"
          />
        </div>
      </div>
      
      <div v-if="saveError" class="error-notification">
        ⚠ AUTO-SAVE FAILED
      </div>
    </div>
  </CRTEffect>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import CRTEffect from './components/CRTEffect.vue'
import HeaderBar from './components/HeaderBar.vue'
import TableView from './components/TableView.vue'
import FileTree from './components/FileTree.vue'

// 状态管理
const config = ref({
  crt_effects: {
    enabled: true,
    distortion: { strength: 0.05, zoom: 1.02 },
    scanlines: { opacity: 0.3, spacing: 2 },
    shadow_mask: { enabled: true, opacity: 0.06 },
    vignette: { strength: 0.5 },
    glow: { strength: '1px', color: 'rgba(255, 255, 255, 0.35)' },
    flicker: { enabled: true, intensity: 0.03 },
    blur: { strength: '0.3px' }
  },
  colors: {
    text_default: '#FFFFFF',
    text_completed: '#555555',
    text_dim: '#888888',
    highlight_bg: 'rgba(255, 255, 255, 0.08)',
    accent: '#00ff41'
  }
})

const allFilesData = ref([])
const currentFileIndex = ref(0)
const currentTableIndex = ref(0)
const dirtyChanges = ref([])
const loading = ref(true)
const error = ref(null)
const saveError = ref(false)
const currentView = ref('file-tree')
const currentFilePath = ref('')
const fileTree = ref([])
const openDirectories = ref(new Set())

let autoSaveInterval = null

// 计算当前标题
const currentTitle = computed(() => {
  if (currentView.value === 'file-tree') {
    return 'FILE MANAGER'
  }
  
  if (allFilesData.value.length === 0) return 'CRT FILE MANAGER'
  
  const currentFile = allFilesData.value[currentFileIndex.value]
  if (!currentFile || currentFile.tables.length === 0) return 'CRT FILE MANAGER'
  
  const currentTable = currentFile.tables[currentTableIndex.value]
  return currentTable ? currentTable.title : 'CRT FILE MANAGER'
})

// 计算当前表格数据
const currentTableData = computed(() => {
  if (allFilesData.value.length === 0) return null
  
  const currentFile = allFilesData.value[currentFileIndex.value]
  if (!currentFile || currentFile.tables.length === 0) return null
  
  return currentFile.tables[currentTableIndex.value]
})

// 计算总表格数
const totalTables = computed(() => {
  if (allFilesData.value.length === 0) return 0
  
  const currentFile = allFilesData.value[currentFileIndex.value]
  return currentFile ? currentFile.tables.length : 0
})

// 构建文件树
const buildFileTree = (files) => {
  const tree = []
  const nodeMap = new Map()
  
  files.forEach(file => {
    const parts = file.filePath.split('/')
    let currentLevel = tree
    
    parts.forEach((part, index) => {
      const isFile = index === parts.length - 1
      const path = parts.slice(0, index + 1).join('/')
      
      let node = nodeMap.get(path)
      
      if (!node) {
        node = {
          name: part,
          path: path,
          type: isFile ? 'file' : 'directory',
          children: []
        }
        
        if (isFile) {
          node.hasTables = file.tables.length > 0
          node.tableCount = file.tables.length
        }
        
        nodeMap.set(path, node)
        currentLevel.push(node)
      }
      
      currentLevel = node.children
    })
  })
  
  return tree
}

// 加载配置文件
const loadConfig = async () => {
  try {
    const response = await fetch('/config.json')
    if (response.ok) {
      config.value = await response.json()
    }
  } catch (e) {
    console.warn('Config load failed, using defaults')
  }
}

// 加载数据结构
const loadStructure = async () => {
  loading.value = true
  error.value = null
  
  try {
    const response = await fetch('/api/structure')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    allFilesData.value = data.files || []
    
    fileTree.value = buildFileTree(allFilesData.value)
    
    currentFileIndex.value = 0
    currentTableIndex.value = 0
    
  } catch (e) {
    error.value = `LOAD FAILED: ${e.message}`
    console.error('Structure load error:', e)
  } finally {
    loading.value = false
  }
}

// 处理表格更新
const handleTableUpdate = (update) => {
  if (!currentTableData.value) return
  
  currentTableData.value.rows = update.rows
  
  const change = {
    filePath: allFilesData.value[currentFileIndex.value].filePath,
    tableIndex: currentTableIndex.value,
    newRows: update.rows
  }
  
  const existingIndex = dirtyChanges.value.findIndex(
    c => c.filePath === change.filePath && c.tableIndex === change.tableIndex
  )
  
  if (existingIndex >= 0) {
    dirtyChanges.value[existingIndex] = change
  } else {
    dirtyChanges.value.push(change)
  }
}

// 保存更改
const saveChanges = async () => {
  if (dirtyChanges.value.length === 0) return
  
  try {
    const response = await fetch('/api/save', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        updates: dirtyChanges.value
      })
    })
    
    const result = await response.json()
    
    if (result.success) {
      dirtyChanges.value = []
      saveError.value = false
    } else {
      saveError.value = true
    }
  } catch (e) {
    console.error('Save failed:', e)
    saveError.value = true
  }
}

// 自动保存
const startAutoSave = () => {
  autoSaveInterval = setInterval(() => {
    if (dirtyChanges.value.length > 0) {
      saveChanges()
    }
  }, 5 * 60 * 1000)
}

const stopAutoSave = () => {
  if (autoSaveInterval) {
    clearInterval(autoSaveInterval)
    autoSaveInterval = null
  }
}

// 切换表格
const prevTable = () => {
  if (currentTableIndex.value > 0) {
    currentTableIndex.value--
  }
}

const nextTable = () => {
  const currentFile = allFilesData.value[currentFileIndex.value]
  if (currentFile && currentTableIndex.value < currentFile.tables.length - 1) {
    currentTableIndex.value++
  }
}

// 选择文件
const selectFile = (filePath) => {
  const fileIndex = allFilesData.value.findIndex(f => f.filePath === filePath)
  if (fileIndex >= 0) {
    currentFileIndex.value = fileIndex
    currentTableIndex.value = 0
    currentFilePath.value = filePath
    currentView.value = 'table'
  }
}

// 显示文件树
const showFileTree = () => {
  currentView.value = 'file-tree'
  currentFilePath.value = ''
}

// 切换目录
const toggleDirectory = (node) => {
  if (openDirectories.value.has(node.path)) {
    openDirectories.value.delete(node.path)
  } else {
    openDirectories.value.add(node.path)
  }
}

// 键盘事件处理
const handleKeydown = (event) => {
  if (event.key === 'Escape' && currentView.value === 'table') {
    showFileTree()
    return
  }
  
  if (currentView.value !== 'table') return
  
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    prevTable()
    return
  }
  
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    nextTable()
    return
  }
}

// 生命周期
onMounted(async () => {
  await loadConfig()
  await loadStructure()
  startAutoSave()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  stopAutoSave()
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
:global(html) {
  overflow-y: scroll;
}

.app-container {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  background-color: transparent;
  overflow: hidden;
}

.content-area {
  flex: 1;
  width: 100%;
  overflow: hidden;
  position: relative;
  background-color: transparent;
  display: flex;
  flex-direction: column;
}

/* === 状态屏幕 (加载/错误/空) === */
.status-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  padding: 20px;
}

.status-icon {
  font-size: 32px;
  color: var(--crt-text);
  text-shadow: 0 0 8px var(--crt-glow-color);
}

.status-text {
  font-size: var(--crt-font-size-sm);
  color: var(--crt-text);
  text-shadow: 0 0 var(--crt-glow-strength) var(--crt-glow-color);
  letter-spacing: 2px;
}

.status-hint {
  font-size: var(--crt-font-size-xs);
  color: var(--crt-text-dim);
  margin-top: 8px;
}

.status-screen.error .status-icon {
  color: #ff4444;
  text-shadow: 0 0 8px rgba(255, 68, 68, 0.5);
}

.status-screen.error .status-text {
  color: #ff4444;
  text-shadow: 0 0 4px rgba(255, 68, 68, 0.5);
}

/* 光标闪烁效果 */
.blink {
  animation: cursor-blink 1s step-end infinite;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.table-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.file-tree-container {
  width: 100%;
  height: 100%;
  overflow: auto;
  box-sizing: border-box;
  background-color: transparent;
  padding: var(--crt-spacing-xl);
}
</style>
