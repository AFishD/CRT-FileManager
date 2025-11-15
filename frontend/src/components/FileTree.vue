<template>
  <div class="file-tree">
    <!-- 根节点（只在最顶层显示） -->
    <div v-if="level === 0" class="root-node">
      Markdown_Tracker/
    </div>
    
    <!-- 文件树内容 -->
    <div class="tree-content">
      <template v-for="(node, index) in treeData" :key="node.path">
        <div class="tree-line">
          <!-- 节点前缀（制表符和连接线） -->
          <span class="tree-prefix">{{ getPrefix(index) }}</span>
          
          <!-- 目录节点 -->
          <div v-if="node.type === 'directory'" class="directory">
            <span class="name">{{ node.name }}/</span>
          </div>
          
          <!-- 文件节点 -->
          <div v-else class="file"
               :class="{ 'has-tables': node.hasTables, 'active': isActive(node) }"
               @click="selectFile(node)">
            <span class="name">{{ node.name }}</span>
            <span v-if="node.tableCount" class="table-count">({{ node.tableCount }})</span>
          </div>
        </div>
        
        <!-- 递归渲染子节点（始终展开） -->
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
  padding: 10px;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  color: #ffffff;
  white-space: pre;
  line-height: 1.4;
}

.root-node {
  font-weight: bold;
  margin-bottom: 10px;
  color: #ffffff;
}

.tree-content {
  margin-left: 0;
}

.tree-line {
  display: flex;
  align-items: center;
  margin: 0;
}

.tree-prefix {
  color: #888888;
  user-select: none;
}

.directory {
  color: #ffffff;
  font-weight: bold;
}

.file {
  cursor: pointer;
  transition: all 0.2s;
  color: #cccccc;
}

.file.has-tables {
  color: #ffffff;
}

.file.has-tables:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.file.active {
  background-color: rgba(255, 255, 255, 0.2);
  color: #ffffff;
}

.name {
  font-size: 14px;
}

.table-count {
  font-size: 12px;
  color: #888888;
  margin-left: 5px;
}

.children {
  margin: 0;
  padding: 0;
}
</style>