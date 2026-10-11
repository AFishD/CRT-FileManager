<template>
  <div class="header-bar">
    <div class="left-section">
      <button v-if="showBackButton" @click="$emit('back')" class="back-btn" title="Back (Esc)">
        ◄
      </button>
      <div
        class="title-wrapper"
        :class="{ clickable: titleClickable }"
        :title="titleClickable ? '表格列表 (点击切换表格)' : ''"
        @click="onTitleClick"
      >
        <span class="title-bracket">[</span>
        <span class="title">{{ title }}</span>
        <span class="title-bracket">]</span>
        <span v-if="titleClickable" class="title-toggle">{{ titleToggle }}</span>
      </div>
    </div>
    <div class="right-section">
      <span v-if="filterLabel" class="filter-badge" title="表头筛选:只显示未完成">
        {{ filterLabel }}
      </span>
      <div class="nav-group" v-if="totalTables > 1">
        <button @click="$emit('prev')" :disabled="!hasPrev" class="nav-btn">
          ◄
        </button>
        <span class="page-indicator">{{ currentTableIndex + 1 }}/{{ totalTables }}</span>
        <button @click="$emit('next')" :disabled="!hasNext" class="nav-btn">
          ►
        </button>
      </div>
      <button @click="$emit('save')" class="save-btn">
        SAVE
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  currentTableIndex: {
    type: Number,
    default: 0
  },
  totalTables: {
    type: Number,
    default: 1
  },
  showBackButton: {
    type: Boolean,
    default: false
  },
  // 标题可点击:多表格文件里点标题展开表格列表
  titleClickable: {
    type: Boolean,
    default: false
  },
  // 标题右侧的展开/收起提示符
  titleToggle: {
    type: String,
    default: '▾'
  },
  // 表头筛选模式下的状态徽标(空串则不显示)
  filterLabel: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['prev', 'next', 'save', 'back', 'title-click'])

const onTitleClick = () => {
  if (props.titleClickable) emit('title-click')
}

const hasPrev = computed(() => props.currentTableIndex > 0)
const hasNext = computed(() => props.currentTableIndex < props.totalTables - 1)
</script>

<style scoped>
.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--crt-spacing-md) var(--crt-spacing-xl);
  background: rgba(0, 0, 0, 0.9);
  min-height: 48px;
  flex-shrink: 0;
  position: relative;
}

/* 下边线与列表列宽同宽(左右内缩一个横向 padding)而不是通栏 ——
   与表格竖线网格对齐,同处一个虚拟 CRT 屏内 */
.header-bar::after {
  content: '';
  position: absolute;
  left: var(--crt-spacing-xl);
  right: var(--crt-spacing-xl);
  bottom: 0;
  height: 1px;
  background: var(--crt-border);
  /* 荧光粉余晖 */
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.05);
}

.left-section {
  display: flex;
  align-items: center;
  gap: var(--crt-spacing-md);
  min-width: 0;
  flex: 1;
}

.back-btn {
  font-size: var(--crt-font-size-sm);
  padding: 6px 10px;
  background: transparent;
  color: var(--crt-text);
  border: 1px solid var(--crt-border);
  flex-shrink: 0;
}

.back-btn:hover {
  background: var(--crt-text);
  color: var(--crt-bg);
  border-color: var(--crt-text);
}

.title-wrapper {
  display: flex;
  align-items: center;
  min-width: 0;
  overflow: hidden;
}

/* 可点击(多表格文件):悬停给反馈,右侧挂一个展开提示符 */
.title-wrapper.clickable {
  cursor: pointer;
  padding: 2px 6px;
  border: 1px solid transparent;
}

.title-wrapper.clickable:hover {
  background: var(--crt-highlight);
  border-color: var(--crt-border);
  box-shadow: 0 0 6px rgba(255, 255, 255, 0.06);
}

.title-toggle {
  color: var(--crt-text-dim);
  font-size: var(--crt-font-size-xs);
  flex-shrink: 0;
  padding: 0 var(--crt-spacing-xs);
}

.title-bracket {
  color: var(--crt-text-dim);
  font-size: var(--crt-font-size-sm);
  flex-shrink: 0;
}

.title {
  font-size: var(--crt-font-size-sm);
  color: var(--crt-text);
  text-shadow: 0 0 var(--crt-glow-strength) var(--crt-glow-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 0 var(--crt-spacing-xs);
  letter-spacing: 1px;
}

.right-section {
  display: flex;
  align-items: center;
  gap: var(--crt-spacing-md);
  flex-shrink: 0;
}

.nav-group {
  display: flex;
  align-items: center;
  gap: var(--crt-spacing-xs);
}

/* 表头筛选模式徽标:强调色边框,一眼看出"现在只看未完成" */
.filter-badge {
  font-size: var(--crt-font-size-xs);
  color: var(--crt-accent);
  border: 1px solid var(--crt-accent);
  padding: 4px 8px;
  letter-spacing: 1px;
  text-shadow: 0 0 var(--crt-glow-strength) var(--crt-accent);
  white-space: nowrap;
}

.page-indicator {
  font-size: var(--crt-font-size-xs);
  color: var(--crt-text-dim);
  min-width: 36px;
  text-align: center;
}

.nav-btn {
  font-size: var(--crt-font-size-xs);
  padding: 6px 8px;
  min-width: 30px;
  background: transparent;
  border: 1px solid var(--crt-border);
}

.save-btn {
  font-size: var(--crt-font-size-xs);
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--crt-border);
  letter-spacing: 1px;
}

.save-btn:hover {
  background: var(--crt-text);
  color: var(--crt-bg);
  border-color: var(--crt-text);
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.2);
}
</style>
