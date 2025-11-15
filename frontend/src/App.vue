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
        <div v-if="loading" class="loading">
          加载中...
        </div>
        
        <div v-else-if="error" class="error">
          {{ error }}
        </div>
        
        <div v-else-if="allFilesData.length === 0" class="empty">
          未找到Markdown文件，请将.md文件放入data目录
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
        上一次自动保存失败
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
    distortion: { strength: 0.03, zoom: 1.01 },
    glow: { strength: "0.5px", color: "rgba(255, 255, 255, 0.4)" },
    blur: { strength: "0.3px" }
  },
  colors: {
    text_default: "#FFFFFF",
    text_completed: "#888888",
    highlight_bg: "rgba(255, 255, 255, 0.1)"
  }
})

const allFilesData = ref([])
const currentFileIndex = ref(0)
const currentTableIndex = ref(0)
const dirtyChanges = ref([])
const loading = ref(true)
const error = ref(null)
const saveError = ref(false)
const currentView = ref('file-tree') // 当前视图: 'file-tree' 或 'table'
const currentFilePath = ref('') // 当前文件路径
const fileTree = ref([]) // 文件树数据
const openDirectories = ref(new Set()) // 打开的目录集合

// 自动保存定时器
let autoSaveInterval = null

// 计算当前标题
const currentTitle = computed(() => {
  if (currentView.value === 'file-tree') {
    return 'CRT Collectibles Tracker - 文件列表'
  }
  
  if (allFilesData.value.length === 0) return 'CRT Collectibles Tracker'
  
  const currentFile = allFilesData.value[currentFileIndex.value]
  if (!currentFile || currentFile.tables.length === 0) return 'CRT Collectibles Tracker'
  
  const currentTable = currentFile.tables[currentTableIndex.value]
  return currentTable ? currentTable.title : 'CRT Collectibles Tracker'
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

// 计算文件树
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
    console.warn('无法加载配置文件，使用默认值')
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
    console.log('加载数据结构:', data)
    allFilesData.value = data.files || []
    
    // 构建文件树
    fileTree.value = buildFileTree(allFilesData.value)
    console.log('文件树构建完成:', fileTree.value)
    
    // 重置索引
    currentFileIndex.value = 0
    currentTableIndex.value = 0
    
  } catch (e) {
    error.value = `加载数据失败: ${e.message}`
    console.error('加载结构失败:', e)
  } finally {
    loading.value = false
  }
}

// 处理表格更新
const handleTableUpdate = (update) => {
  if (!currentTableData.value) return
  
  // 更新当前表格数据
  currentTableData.value.rows = update.rows
  
  // 记录更改
  const change = {
    filePath: allFilesData.value[currentFileIndex.value].filePath,
    tableIndex: currentTableIndex.value,
    newRows: update.rows
  }
  
  // 检查是否已存在相同文件和表格的更改
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
      console.log('保存成功')
      dirtyChanges.value = []
      saveError.value = false
    } else {
      console.error('保存失败:', result.message)
      saveError.value = true
    }
  } catch (e) {
    console.error('保存请求失败:', e)
    saveError.value = true
  }
}

// 自动保存
const startAutoSave = () => {
  // 每5分钟自动保存一次
  autoSaveInterval = setInterval(() => {
    if (dirtyChanges.value.length > 0) {
      saveChanges()
    }
  }, 5 * 60 * 1000) // 5分钟
}

// 停止自动保存
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
  console.log('键盘事件:', event.key, '当前视图:', currentView.value)
  
  // ESC键返回文件树
  if (event.key === 'Escape' && currentView.value === 'table') {
    console.log('ESC键触发，返回文件树')
    showFileTree()
    return
  }
  
  // 只在表格视图中处理其他键盘事件
  if (currentView.value !== 'table') return
  
  // 左右箭头键切换表格
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

// 生命周期钩子
onMounted(async () => {
  console.log('App mounted, 初始化应用...')
  await loadConfig()
  await loadStructure()
  startAutoSave()
  
  // 添加键盘事件监听
  window.addEventListener('keydown', handleKeydown)
  console.log('键盘事件监听已添加')
})

onUnmounted(() => {
  stopAutoSave()
  
  // 移除键盘事件监听
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
:global(html) {
  /* 强制垂直滚动条始终存在（或为其保留空间） */
  /* 这可以防止因内容变化导致滚动条出现/消失而引起的页面抖动 */
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
  overflow: hidden; /* 关键修复：剪裁溢出的子元素 */
  position: relative;
  background-color: transparent;
  display: flex;
  flex-direction: column;
}

.loading, .error, .empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 14px;
  padding: 20px;
}

.error {
  color: #ff0000;
}

.empty {
  color: #888888;
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
  padding: 20px;
}
</style>