<template>
  <div class="table-list">
    <!-- 根节点:当前文件 -->
    <div class="root-node">
      <span class="root-icon">■</span>
      <span class="root-text">{{ fileName || 'FILE' }}</span>
      <span class="root-count">[{{ tables.length }} TABLES]</span>
    </div>

    <!-- 文件内表格列表 -->
    <div class="list-content">
      <div
        v-for="(table, index) in tables"
        :key="index"
        :ref="el => { if (el) itemRefs[index] = el }"
        class="list-line"
        :class="{ 'active': index === currentIndex, 'selected': index === selectedIndex }"
        @click="select(index)"
      >
        <span class="tree-prefix">{{ index === tables.length - 1 ? '└── ' : '├── ' }}</span>
        <span class="table-icon">◈</span>
        <span class="table-title">{{ table.title || `表格 ${index + 1}` }}</span>
        <span v-if="progressOf(table).total" class="table-progress">
          {{ progressOf(table).done }}/{{ progressOf(table).total }}
        </span>
      </div>
    </div>

    <div class="list-hint">↑↓ 选择 · ENTER 切换 · ESC 返回</div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  tables: {
    type: Array,
    default: () => []
  },
  currentIndex: {
    type: Number,
    default: 0
  },
  fileName: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['select'])

const itemRefs = ref([])
const selectedIndex = ref(props.currentIndex)

// 进度列(最后一列)里 [x] 的条数 / 数据行数;分隔行(空数组)不计入
const progressOf = (table) => {
  const rows = (table && table.rows) || []
  const dataRows = rows.filter(r => Array.isArray(r) && r.length > 0)
  const done = dataRows.filter(r => String(r[r.length - 1] ?? '').trim() === '[x]').length
  return { done, total: dataRows.length }
}

const scrollSelectedIntoView = () => {
  const el = itemRefs.value[selectedIndex.value]
  if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' })
}

const select = (index) => {
  if (index < 0 || index >= props.tables.length) return
  emit('select', index)
}

const moveSelection = (delta) => {
  const next = selectedIndex.value + delta
  if (next < 0 || next >= props.tables.length) return
  selectedIndex.value = next
}

const handleKeydown = (event) => {
  switch (event.key) {
    case 'ArrowUp':
      event.preventDefault()
      moveSelection(-1)
      break
    case 'ArrowDown':
      event.preventDefault()
      moveSelection(1)
      break
    case 'Enter':
    case ' ':
      event.preventDefault()
      select(selectedIndex.value)
      break
  }
}

watch(selectedIndex, () => {
  nextTick(scrollSelectedIntoView)
})

// 父组件切换当前表格(如 ←/→ 快捷键)时,跟随高亮
watch(() => props.currentIndex, (index) => {
  selectedIndex.value = index
})

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  nextTick(scrollSelectedIntoView)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.table-list {
  padding: var(--crt-spacing-md);
  font-family: var(--crt-font);
  font-size: var(--crt-font-size-sm);
  color: var(--crt-text);
  white-space: pre;
  line-height: 1.8;
  /* 荧光粉余晖 */
  text-shadow: 0 0 var(--crt-glow-strength) var(--crt-glow-color);
}

.root-node {
  font-weight: bold;
  margin-bottom: var(--crt-spacing-md);
  color: var(--crt-text);
  display: flex;
  align-items: center;
  gap: var(--crt-spacing-sm);
  padding-bottom: var(--crt-spacing-sm);
  border-bottom: 1px solid var(--crt-border);
  white-space: normal;
}

.root-icon {
  color: var(--crt-text);
}

.root-text {
  letter-spacing: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.root-count {
  color: var(--crt-text-dim);
  font-size: var(--crt-font-size-xs);
  flex-shrink: 0;
}

.list-content {
  margin-left: 0;
}

.list-line {
  display: flex;
  align-items: center;
  gap: var(--crt-spacing-xs);
  margin: 0;
  padding: 1px 4px;
  cursor: pointer;
  color: var(--crt-text-dim);
  transition: all 0.15s ease;
}

.list-line:hover {
  background-color: var(--crt-highlight);
  box-shadow: 0 0 4px rgba(255, 255, 255, 0.05);
}

/* 键盘光标 */
.list-line.selected {
  background-color: var(--crt-highlight);
}

/* 当前正在显示的表格 */
.list-line.active {
  background-color: var(--crt-highlight-strong);
  color: var(--crt-text);
  box-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
}

.tree-prefix {
  color: var(--crt-border);
  user-select: none;
}

.table-icon {
  color: var(--crt-text-dim);
  font-size: var(--crt-font-size-xs);
}

.list-line.active .table-icon {
  color: var(--crt-text);
}

.table-title {
  font-size: var(--crt-font-size-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.table-progress {
  margin-left: auto;
  padding-left: var(--crt-spacing-md);
  font-size: var(--crt-font-size-xs);
  color: var(--crt-text-dim);
  flex-shrink: 0;
}

.list-hint {
  margin-top: var(--crt-spacing-md);
  padding-top: var(--crt-spacing-sm);
  border-top: 1px solid var(--crt-border);
  font-size: var(--crt-font-size-xs);
  color: var(--crt-text-dim);
  letter-spacing: 1px;
}
</style>
