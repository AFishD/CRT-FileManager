<template>
  <div class="header-bar">
    <div class="left-section">
      <button v-if="showBackButton" @click="$emit('back')" class="back-btn" title="返回文件列表 (Esc)">
        ←
      </button>
      <div class="title">{{ title }}</div>
    </div>
    <div class="nav-buttons">
      <button @click="$emit('prev')" :disabled="!hasPrev" class="nav-btn">
        ←
      </button>
      <button @click="$emit('next')" :disabled="!hasNext" class="nav-btn">
        →
      </button>
      <button @click="$emit('save')" class="save-btn">
        保存
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
  padding: 20px;
  background: rgba(0, 0, 0, 0.8);
  border-bottom: 2px solid #ffffff;
}

.left-section {
  display: flex;
  align-items: center;
  gap: 15px;
}

.back-btn {
  font-size: 14px;
  padding: 8px 12px;
  background: #333333;
  color: #ffffff;
  border: 1px solid #ffffff;
  cursor: pointer;
  transition: all 0.2s;
}

.back-btn:hover {
  background: #ffffff;
  color: #000000;
}

.title {
  font-size: 16px;
  color: #ffffff;
  text-shadow: 0 0 10px #ffffff;
}

.nav-buttons {
  display: flex;
  gap: 10px;
}

.nav-btn, .save-btn {
  font-size: 10px;
  padding: 8px 12px;
  min-width: 60px;
}

.save-btn {
  background: #ffffff;
  color: #000000;
}

.save-btn:hover {
  background: #000000;
  color: #ffffff;
}
</style>