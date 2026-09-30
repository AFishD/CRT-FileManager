<template>
  <div class="header-bar">
    <div class="left-section">
      <button v-if="showBackButton" @click="$emit('back')" class="back-btn" title="Back (Esc)">
        ◄
      </button>
      <div class="title-wrapper">
        <span class="title-bracket">[</span>
        <span class="title">{{ title }}</span>
        <span class="title-bracket">]</span>
      </div>
    </div>
    <div class="right-section">
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
  }
})

defineEmits(['prev', 'next', 'save', 'back'])

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
