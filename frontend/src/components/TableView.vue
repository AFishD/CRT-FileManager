<template>
  <div class="table-view-container">
    <div
      class="table-view"
      ref="scrollContainerRef"
      :style="{ scrollPaddingTop: `${headerHeight}px` }"
      @wheel="handleWheel"
      tabindex="0"
    >
      <table>
        <colgroup>
          <col 
            v-for="(width, index) in columnWidths" 
            :key="`col-${index}`" 
            :style="{ width: width > 0 ? `${width}px` : '' }"
          />
        </colgroup>

        <thead ref="headerRef">
          <tr>
            <th v-for="(header, index) in visibleHeader" :key="index">
              {{ header }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in visibleRows"
            :key="index"
            :ref="el => { if (el) rowRefs[index] = el }"
            :class="{
              'highlight': highlightedRowIndex === index,
              'completed': isRowCompleted(index),
              'separator-row': isSeparatorRow(index)
            }"
            @click="handleRowClick(index)"
          >
            <td v-for="(cell, cellIndex) in row" :key="cellIndex" v-if="!isSeparatorRow(index)">
              <div class="marquee-container">
                <span class="marquee-text-part">{{ cell }}</span>
              </div>
            </td>
            <td v-else :colspan="visibleHeader.length" class="separator-cell">
              &nbsp;
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps({
  tableData: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update'])

const selectedRowIndex = ref(0)
const scrollContainerRef = ref(null)
const rowRefs = ref([])
const headerRef = ref(null)
const headerHeight = ref(0)
const columnWidths = ref([])

const calculateColumnWidths = async () => {
  await nextTick();

  const containerEl = scrollContainerRef.value;
  if (!containerEl || !visibleHeader.value.length) {
    columnWidths.value = [];
    return;
  }

  const computedStyle = getComputedStyle(containerEl);
  const paddingX = parseFloat(computedStyle.paddingLeft) + parseFloat(computedStyle.paddingRight);
  const containerWidth = containerEl.clientWidth - paddingX;

  const CELL_PADDING = 20;
  const MAX_WIDTH = 500;
  const MIN_WIDTH = 60;
  
  const numColumns = visibleHeader.value.length;
  const idealWidths = new Array(numColumns).fill(0);
  
  const measurer = document.createElement('span');
  measurer.style.position = 'absolute';
  measurer.style.visibility = 'hidden';
  measurer.style.whiteSpace = 'nowrap';
  measurer.style.fontSize = '10px';
  measurer.style.fontFamily = "'Press Start 2P', monospace";
  document.body.appendChild(measurer);

  for (let i = 0; i < numColumns; i++) {
    let maxContentWidth = 0;
    measurer.textContent = visibleHeader.value[i];
    maxContentWidth = measurer.getBoundingClientRect().width;

    visibleRows.value.forEach(row => {
      if (Array.isArray(row) && row[i] != null) {
        measurer.textContent = row[i];
        const contentWidth = measurer.getBoundingClientRect().width;
        if (contentWidth > maxContentWidth) {
          maxContentWidth = contentWidth;
        }
      }
    });

    idealWidths[i] = Math.min(maxContentWidth + CELL_PADDING, MAX_WIDTH);
  }
  document.body.removeChild(measurer);

  const totalIdealWidth = idealWidths.reduce((sum, w) => sum + w, 0);
  let finalWidths = [];

  if (totalIdealWidth <= containerWidth) {
    const stretchRatio = containerWidth / totalIdealWidth;
    finalWidths = idealWidths.map(w => w * stretchRatio);
  } else {
    const overflowWidth = totalIdealWidth - containerWidth;
    
    const shrinkableSpaces = idealWidths.map(w => Math.max(0, w - MIN_WIDTH));
    const totalShrinkableSpace = shrinkableSpaces.reduce((sum, s) => sum + s, 0);

    if (totalShrinkableSpace <= 0) {
      finalWidths = idealWidths.map(() => MIN_WIDTH);
    } else {
      finalWidths = idealWidths.map((idealW, i) => {
        const shrinkRatio = shrinkableSpaces[i] / totalShrinkableSpace;
        const reduction = overflowWidth * shrinkRatio;
        return Math.max(MIN_WIDTH, idealW - reduction);
      });
    }
  }

  columnWidths.value = finalWidths;
  
  await nextTick();
  updateMarqueeEffects();
};

const updateHeaderHeight = () => {
  if (headerRef.value) {
    headerHeight.value = headerRef.value.offsetHeight + 20;
  }
}

const updateMarqueeEffects = () => {
  if (!scrollContainerRef.value) return;
  const dataCells = scrollContainerRef.value.querySelectorAll('td:not(.separator-cell)');
  dataCells.forEach(td => {
    const container = td.querySelector('.marquee-container');
    const part = td.querySelector('.marquee-text-part');
    if (!container || !part) return;
    td.classList.remove('is-overflowing');
    const clonedPart = container.querySelector('.marquee-text-part.cloned');
    if (clonedPart) container.removeChild(clonedPart);
    if (part.scrollWidth > td.clientWidth) {
      td.classList.add('is-overflowing');
      const clone = part.cloneNode(true);
      clone.classList.add('cloned');
      container.appendChild(clone);
      const scrollDistance = part.scrollWidth + 40;
      const duration = scrollDistance / 50;
      container.style.setProperty('--duration', `${Math.max(3, duration)}s`);
    }
  });
}

watch(() => props.tableData, () => {
  calculateColumnWidths();
}, { deep: true, immediate: true });

watch(selectedRowIndex, (newIndex) => {
  const container = scrollContainerRef.value;
  const rowElement = rowRefs.value[newIndex];

  if (!container || !rowElement) return;

  const viewTop = container.scrollTop + headerHeight.value;
  const viewBottom = container.scrollTop + container.clientHeight;
  const rowTop = rowElement.offsetTop;
  const rowBottom = rowElement.offsetTop + rowElement.offsetHeight;

  let newScrollTop = container.scrollTop;

  if (rowTop < viewTop) {
    newScrollTop = rowTop - headerHeight.value;
  } else if (rowBottom > viewBottom) {
    newScrollTop = rowBottom - container.clientHeight;
  }

  if (newScrollTop !== container.scrollTop) {
    container.scrollTo({
      top: newScrollTop,
      behavior: 'smooth'
    });
  }
}, { flush: 'post' });


onMounted(() => {
  nextTick(() => {
    updateHeaderHeight();
    if (scrollContainerRef.value) {
        scrollContainerRef.value.scrollTop = 0;
    }
    scrollContainerRef.value?.focus();
  });

  window.addEventListener('keydown', handleKeydown);

  const resizeObserver = new ResizeObserver(() => {
    calculateColumnWidths();
    updateHeaderHeight();
  });
  
  if (scrollContainerRef.value) {
    resizeObserver.observe(scrollContainerRef.value);
  }

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
    resizeObserver.disconnect();
  });
})

const visibleHeader = computed(() => {
  if (!props.tableData.header) return [];
  return props.tableData.header.slice(0, -1);
});

const visibleRows = computed(() => {
  if (!props.tableData.rows) return [];
  return props.tableData.rows.map(row => {
    if (Array.isArray(row) && row.length > 0) {
      return row.slice(0, -1);
    }
    return row;
  });
});

const progressColumnIndex = computed(() => props.tableData.header.length - 1)

const highlightedRowIndex = computed(() => selectedRowIndex.value)

const isRowCompleted = (rowIndex) => {
  if (progressColumnIndex.value === -1) return false
  const row = props.tableData.rows[rowIndex]
  return row && row[progressColumnIndex.value] === '[x]'
}
const isSeparatorRow = (rowIndex) => {
  const row = props.tableData.rows[rowIndex]
  return row === null || row === undefined || (Array.isArray(row) && row.length === 0)
}
const toggleRowCompletion = (rowIndex) => {
  if (progressColumnIndex.value === -1) return
  
  const row = props.tableData.rows[rowIndex]
  if (!row || row.length === 0) return
  
  row[progressColumnIndex.value] = row[progressColumnIndex.value] === '[x]' ? '[ ]' : '[x]'
  
  emit('update', {
    rows: [...props.tableData.rows]
  })
}
const handleRowClick = (rowIndex) => {
  if (isSeparatorRow(rowIndex)) return
  
  selectedRowIndex.value = rowIndex
  toggleRowCompletion(rowIndex)
}
const moveSelectionUp = () => {
  let newIndex = selectedRowIndex.value - 1
  while (newIndex >= 0 && isSeparatorRow(newIndex)) {
    newIndex--
  }
  if (newIndex >= 0) {
    selectedRowIndex.value = newIndex
  }
}
const moveSelectionDown = () => {
  const rows = props.tableData.rows
  let newIndex = selectedRowIndex.value + 1
  while (newIndex < rows.length && isSeparatorRow(newIndex)) {
    newIndex++
  }
  if (newIndex < rows.length) {
    selectedRowIndex.value = newIndex
  }
}
const handleWheel = (event) => {
  event.preventDefault()
  if (event.deltaY < 0) {
    moveSelectionUp()
  } else if (event.deltaY > 0) {
    moveSelectionDown()
  }
}
const handleKeydown = (event) => {
  switch (event.key) {
    case 'ArrowUp':
      event.preventDefault()
      moveSelectionUp()
      break
    
    case 'ArrowDown':
      event.preventDefault()
      moveSelectionDown()
      break
    
    case ' ':
    case 'Enter':
      event.preventDefault()
      if (!isSeparatorRow(selectedRowIndex.value)) {
        toggleRowCompletion(selectedRowIndex.value)
      }
      break
  }
}

</script>

<style scoped>
.table-view-container {
  flex-grow: 1;
  height: 100%;
  width: 100%;
  padding-bottom: 36px;
  box-sizing: border-box;
}

.table-view {
  height: 100%;
  width: 100%;
  overflow-y: auto;
  outline: none;
  padding: 0 var(--crt-spacing-xl);
  box-sizing: border-box;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.table-view::-webkit-scrollbar {
  display: none;
}

table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0 6px;
  table-layout: fixed;
}

thead {
  background-color: transparent;
}

th {
  position: sticky;
  top: 16px;
  z-index: 10;
  background: var(--crt-bg);
  color: var(--crt-text);
  border: none;
  border-bottom: 1px solid var(--crt-border);
  font-size: var(--crt-font-size-xs);
  padding: var(--crt-spacing-sm) var(--crt-spacing-sm);
  text-transform: uppercase;
  text-align: center;
  letter-spacing: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  box-sizing: border-box;
  /* 扫描线上的荧光粉效果 */
  text-shadow: 0 0 var(--crt-glow-strength) var(--crt-glow-color);
  /* 粘性表头阴影 */
  box-shadow: 0 -16px 0 0 var(--crt-bg);
}

th:first-child {
  border-left: 1px solid var(--crt-border);
}

th:last-child {
  border-right: 1px solid var(--crt-border);
}

tbody {
  border-top: 6px solid transparent;
}

tr {
  cursor: pointer;
  transition: all 0.1s ease;
}

tr:not(.separator-row):not(.completed):hover td {
  background-color: var(--crt-highlight);
}

tr.highlight td {
  background-color: var(--crt-highlight-strong);
  box-shadow: inset 0 0 4px rgba(255, 255, 255, 0.03);
}

td {
  font-size: var(--crt-font-size-sm);
  padding: 6px var(--crt-spacing-sm);
  border: none;
  border-left: 1px solid var(--crt-border);
  transition: all 0.1s;
  height: 32px;
  box-sizing: border-box;
  white-space: nowrap;
  overflow: hidden;
  vertical-align: middle;
  /* 荧光粉余晖 */
  text-shadow: 0 0 var(--crt-glow-strength) var(--crt-glow-color);
}

td:last-child {
  border-right: 1px solid var(--crt-border);
}

/* === 已完成行 === */
tr.completed td {
  color: var(--crt-text-completed);
  border-left-color: rgba(85, 85, 85, 0.3);
  border-right-color: rgba(85, 85, 85, 0.3);
  text-decoration: line-through;
  text-shadow: none;
}

/* === 分隔行 === */
tr.separator-row td {
  border: none !important;
  background-color: transparent;
  padding: 0;
  height: 24px;
}

/* === 跑马灯 (Marquee) === */
@keyframes marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

td > div.marquee-container {
  display: flex;
  width: fit-content;
  animation: marquee var(--duration) linear infinite;
  animation-play-state: paused;
}

.marquee-text-part {
  white-space: nowrap;
  margin-right: 40px;
}

td.is-overflowing > div.marquee-container {
  animation-play-state: running;
}
</style>
