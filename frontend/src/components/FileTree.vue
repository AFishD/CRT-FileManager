<template>
  <div class="file-tree">
    <!-- 根节点（只在最顶层显示） -->
    <div v-if="level === 0" class="root-node">
      <span class="root-icon">■</span>
      <span class="root-text">DATA/</span>
    </div>
    
    <!-- 文件树内容 -->
    <div class="tree-content">
      <template v-for="(node, index) in treeData" :key="node.path">
        <div class="tree-line">
          <!-- 节点前缀（制表符和连接线） -->
          <span class="tree-prefix">{{ getPrefix(index) }}</span>
          
          <!-- 目录节点 -->
          <div v-if="node.type === 'directory'" class="directory">
            <span class="dir-icon">▸</span>
            <span class="name">{{ node.name }}/</span>
          </div>
          
          <!-- 文件节点 -->
          <div v-else class="file"
               :class="{ 'has-tables': node.hasTables, 'active': isActive(node) }"
               @click="selectFile(node)">
            <span class="file-icon">{{ node.hasTables ? '◈' : '◇' }}</span>
            <span class="name">{{ node.name }}</span>
            <span v-if="node.tableCount" class="table-count">[{{ node.tableCount }}]</span>
          </div>
        </div>
        
        <!-- 递归渲染子节点 -->
        <div v-if="node.type === 'directory' && node.children && node.children.length > 0" class="children">
          <FileTree
            :treeData="node.children"
            :level="level + 1"
            :currentFile="currentFile"
            @file-select="$emit('file-select', $event)"
            :parentPrefix="getChildPrefix(index)" />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  treeData: {
    type: Array,
    default: () => []
  },
  level: {
    type: Number,
    default: 0
  },
  currentFile: {
    type: String,
    default: ''
  },
  parentPrefix: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['file-select'])

const isActive = (node) => {
  return node.type === 'file' && node.path === props.currentFile
}

const selectFile = (node) => {
  if (node.type === 'file' && node.hasTables) {
    emit('file-select', node.path)
  }
}

const getPrefix = (index) => {
  const isLast = index === props.treeData.length - 1
  const prefix = isLast ? '└── ' : '├── '
  
  if (props.level === 0) {
    return prefix
  }
  return props.parentPrefix + prefix
}

const getChildPrefix = (index) => {
  const isLast = index === props.treeData.length - 1
  const prefix = isLast ? '    ' : '│   '
  
  if (props.level === 0) {
    return prefix
  }
  return props.parentPrefix + prefix
}
</script>

<style scoped>
.file-tree {
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
}

.root-icon {
  color: var(--crt-text);
}

.root-text {
  letter-spacing: 2px;
}

.tree-content {
  margin-left: 0;
}

.tree-line {
  display: flex;
  align-items: center;
  margin: 0;
  padding: 1px 0;
}

.tree-prefix {
  color: var(--crt-border);
  user-select: none;
}

.directory {
  color: var(--crt-text);
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: var(--crt-spacing-xs);
}

.dir-icon {
  color: var(--crt-text-dim);
  font-size: var(--crt-font-size-xs);
}

.file {
  cursor: pointer;
  transition: all 0.15s ease;
  color: var(--crt-text-dim);
  display: flex;
  align-items: center;
  gap: var(--crt-spacing-xs);
  padding: 1px 4px;
}

.file-icon {
  font-size: var(--crt-font-size-xs);
}

.file.has-tables {
  color: var(--crt-text);
}

.file.has-tables:hover {
  background-color: var(--crt-highlight);
  box-shadow: 0 0 4px rgba(255, 255, 255, 0.05);
}

.file.active {
  background-color: var(--crt-highlight-strong);
  color: var(--crt-text);
  box-shadow: 0 0 6px rgba(255, 255, 255, 0.08);
}

.name {
  font-size: var(--crt-font-size-sm);
}

.table-count {
  font-size: var(--crt-font-size-xs);
  color: var(--crt-text-dim);
  margin-left: var(--crt-spacing-xs);
}

.children {
  margin: 0;
  padding: 0;
}
</style>
