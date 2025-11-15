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
        <!-- CHANGED: Add colgroup to apply calculated column widths -->
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

// --- Existing Refs ---
const selectedRowIndex = ref(0)
const scrollContainerRef = ref(null)
const rowRefs = ref([])
const headerRef = ref(null)
const headerHeight = ref(0)

// --- CHANGED: New Ref for column widths ---
const columnWidths = ref([])


// --- FIXED: 核心算法修正 ---
const calculateColumnWidths = async () => {
  await nextTick();

  const containerEl = scrollContainerRef.value;
  if (!containerEl || !visibleHeader.value.length) {
    columnWidths.value = [];
    return;
  }

  // --- Stage 1: Constants & Initialization ---

  // FIXED (1/3): 正确计算容器的可用净宽度
  const computedStyle = getComputedStyle(containerEl);
  const paddingX = parseFloat(computedStyle.paddingLeft) + parseFloat(computedStyle.paddingRight);
  const containerWidth = containerEl.clientWidth - paddingX;

  // FIXED (2/3): 修正CELL_PADDING以匹配CSS
  const CELL_PADDING = 20; // 10px left + 10px right from CSS
  const MAX_WIDTH = 500;
  const MIN_WIDTH = 60;
  
  const numColumns = visibleHeader.value.length;
  const idealWidths = new Array(numColumns).fill(0);
  
  // --- Stage 2: Measure & Calculate Ideal Widths ---
  const measurer = document.createElement('span');
  measurer.style.position = 'absolute';
  measurer.style.visibility = 'hidden';
  measurer.style.whiteSpace = 'nowrap';
  // Match font styles from the table cells for accurate measurement
  measurer.style.fontSize = '10px';
  document.body.appendChild(measurer);

  for (let i = 0; i < numColumns; i++) {
    // Include header in measurement
    let maxContentWidth = 0;
    measurer.textContent = visibleHeader.value[i];
    maxContentWidth = measurer.getBoundingClientRect().width;

    // Measure all cells in the column
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
  document.body.removeChild(measurer); // Cleanup

  // --- Stage 3: Decision & Final Width Calculation ---
  const totalIdealWidth = idealWidths.reduce((sum, w) => sum + w, 0);
  let finalWidths = [];

  if (totalIdealWidth <= containerWidth) {
    // Scenario A: Un-overflowed - Stretch to fill
    const stretchRatio = containerWidth / totalIdealWidth;
    finalWidths = idealWidths.map(w => w * stretchRatio);
  } else {
    // Scenario B: Overflowed - Shrink proportionally
    const overflowWidth = totalIdealWidth - containerWidth;
    
    const shrinkableSpaces = idealWidths.map(w => Math.max(0, w - MIN_WIDTH));
    const totalShrinkableSpace = shrinkableSpaces.reduce((sum, s) => sum + s, 0);

    if (totalShrinkableSpace <= 0) {
      // Edge case: cannot shrink further
      finalWidths = idealWidths.map(() => MIN_WIDTH);
    } else {
      finalWidths = idealWidths.map((idealW, i) => {
        const shrinkRatio = shrinkableSpaces[i] / totalShrinkableSpace;
        const reduction = overflowWidth * shrinkRatio;
        return Math.max(MIN_WIDTH, idealW - reduction);
      });
    }
  }

  // --- Stage 4: Apply ---
  columnWidths.value = finalWidths;
  
  // Recalculate marquee effects after widths are applied
  await nextTick();
  updateMarqueeEffects();
};


// --- Existing Logic ---
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

// CHANGED: Watch for data changes to recalculate widths
watch(() => props.tableData, () => {
  calculateColumnWidths();
}, { deep: true, immediate: true });


// Scrolling logic remains the same
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
    // Initial width calculation is handled by the immediate watch
    if (scrollContainerRef.value) {
        scrollContainerRef.value.scrollTop = 0;
    }
    scrollContainerRef.value?.focus();
  });

  window.addEventListener('keydown', handleKeydown);

  // CHANGED: Use ResizeObserver to recalculate widths on container resize
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

// --- Computed properties from previous step (unchanged) ---
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


// --- All event handlers and helper functions remain the same ---
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
  if (!row || row.length === 0) return // 禁止对分隔行进行操作
  
  // 切换进度状态
  row[progressColumnIndex.value] = row[progressColumnIndex.value] === '[x]' ? '[ ]' : '[x]'
  
  // 发出更新事件
  emit('update', {
    rows: [...props.tableData.rows] // 发送副本
  })
}
const handleRowClick = (rowIndex) => {
  // 如果点击的是分隔行，不进行处理
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
  // 阻止默认的像素滚动
  event.preventDefault()

  // 根据滚轮方向调用相应的移动函数
  if (event.deltaY < 0) {
    // 向上滚动
    moveSelectionUp()
  } else if (event.deltaY > 0) {
    // 向下滚动
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
/* All styles remain the same. The `table-layout: fixed` rule is */
/* crucial for the <col> widths to be respected correctly. */
/* ... (no changes to CSS) ... */
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
  padding: 0 20px;
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
  border-spacing: 0 10px;
  table-layout: fixed; /* This is important for <col> to work reliably */
}
thead {
  background-color: #ffffff;
}
th {
  position: sticky;
  top: 20px;
  z-index: 10;
  background: #ffffff;
  color: #000000;
  box-shadow: 0 -20px 0 0 #000000;
  border: none;
  border-bottom: 2px solid #333333;
  font-size: 10px;
  padding: 10px;
  text-transform: uppercase;
  text-align: center;
  
  /* CHANGED: Add overflow hidden to prevent text from spilling out of th */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  /* FIXED (3/3): 添加 box-sizing */
  box-sizing: border-box;
}
th:first-child {
  border-left: 2px solid #333333;
}
th:last-child {
  border-right: 2px solid #333333;
}
tbody {
  border-top: 10px solid #000000;
}
td {
  font-size: 10px;
  padding: 8px 10px;
  border: none;
  border-left: 2px solid #ffffff;
  transition: all 0.1s;
  height: 36px;
  box-sizing: border-box;
  white-space: nowrap;
  overflow: hidden;
  vertical-align: middle;

  /* FIXED (3/3): 添加 box-sizing */
  box-sizing: border-box;
}
td:last-child {
  border-right: 2px solid #ffffff;
}
tr.completed td {
  border-left-color: #888888;
  border-right-color: #888888;
}
tr.separator-row td {
  border: none !important;
  background-color: transparent;
  padding: 0;
  height: 36px;
}
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