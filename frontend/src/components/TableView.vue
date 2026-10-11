<template>
  <div class="table-view-container">
    <div
      class="table-view"
      :class="{ filtered: isFiltered }"
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

        <!-- 点表头切换筛选模式:只显示"点击那一刻还未完成"的行 -->
        <thead ref="headerRef" @click="toggleFilter">
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
              'highlight': index === selectedRowIndex || index === clickLitIndex,
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
      <!-- 不足一页时的"空行"填充:左右边框与列网格同宽,内部无分隔线。
           筛选后一行不剩时,提示就挂在这块空行区顶部(表头正下方) -->
      <div
        class="table-empty-fill"
        v-show="emptyFillHeight > 0"
        :style="{ height: emptyFillHeight + 'px' }"
      >
        <div v-if="isFiltered && displayIndexes.length === 0" class="table-filter-empty">
          NO UNFINISHED ROWS
        </div>
      </div>
    </div>
    <!-- 吸收"已拟合整行"与容器底部之间的空隙,并补上左右边框,
         让表格框架一直连到底部横线(横线因此固定在页面底部,不随内容浮动) -->
    <div class="table-frame-fill" v-show="fittedHeight > 0"></div>
    <!-- 底部横线:普通文档流元素(紧跟滚动区之后)。
         不用绝对定位 —— foreignObject 快照的全新布局中,绝对定位
         相对 vh 替换后的 flex 祖先会漂移 ~20px,导致线压到末行上 -->
    <div class="table-bottom-line" v-show="fittedHeight > 0"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps({
  tableData: {
    type: Object,
    required: true
  },
  // 表头筛选:点击表头时冻结下来的"未完成行"原始下标;null = 未筛选
  filterIndexes: {
    type: Array,
    default: null
  }
})

const emit = defineEmits(['update', 'toggle-filter'])

const selectedRowIndex = ref(0)   // 键盘光标:只由 ↑↓ / 空格 / 回车 移动
const clickLitIndex = ref(-1)     // 鼠标点击点亮的行(纯视觉,不影响键盘光标)
const scrollContainerRef = ref(null)
const rowRefs = ref([])
const headerRef = ref(null)
const headerHeight = ref(0)
const columnWidths = ref([])

// === 筛选模式:显示哪些行 ===
// 未筛选 = 全部行(含分隔行);筛选 = 只显示"点击表头那一刻还未完成"的行。
// 下标在点击时冻结一次,之后勾选/取消都不会让行从列表里增删
// (即:记录后手动改成已完成的行仍然留在列表里,只是变成已完成样式)。
// 组件里所有"行下标"都指显示下标,rowAt() 负责换算回真实行。
const isFiltered = computed(() => Array.isArray(props.filterIndexes))
const displayIndexes = computed(() => {
  const rows = props.tableData.rows || []
  if (!Array.isArray(props.filterIndexes)) return rows.map((_, i) => i)
  return props.filterIndexes.filter(i => i >= 0 && i < rows.length)
})
const rowAt = (displayIndex) => (props.tableData.rows || [])[displayIndexes.value[displayIndex]]

// === 选中行"荧光"点亮/熄灭 ===
// 用 JS 逐帧驱动透明度而不是 CSS transition:快照克隆体是全新渲染,
// CSS 过渡的中间态不会进入快照,画面会瞬间跳到终值;JS 每帧写一次
// 样式变量,每次变更都触发快照,渐隐才能在画面上真正可见。
//
// 键盘行与鼠标点击行各有一条独立时间线:点鼠标不会移动键盘光标,
// 也不会把键盘行的余晖掐掉;每条时间线只写自己那一行的 --sel-alpha
const LIT_HOLD_MS = 600
const FADE_MS = 700

const createGlow = () => {
  let index = -1
  let raf = 0
  let timer = null

  const setAlpha = (value) => {
    const row = rowRefs.value[index]
    if (row && row.style) row.style.setProperty('--sel-alpha', String(value))
  }

  const startFade = () => {
    const t0 = performance.now()
    const step = (t) => {
      const k = Math.min(1, (t - t0) / FADE_MS)
      // 二次衰减曲线:先快后慢,接近荧光粉熄灭的物理感受
      setAlpha(Math.pow(1 - k, 2))
      raf = k < 1 ? requestAnimationFrame(step) : 0
    }
    raf = requestAnimationFrame(step)
  }

  return {
    light(nextIndex) {
      cancelAnimationFrame(raf)
      clearTimeout(timer)
      // 换行点亮:上一行立即熄灭(否则它的渐隐被打断会留下残亮)
      if (index !== -1 && index !== nextIndex) setAlpha(0)
      index = nextIndex
      setAlpha(1)
      timer = setTimeout(startFade, LIT_HOLD_MS)
    },
    dispose() {
      cancelAnimationFrame(raf)
      clearTimeout(timer)
    }
  }
}

const keyboardGlow = createGlow()
const clickGlow = createGlow()

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
  measurer.style.fontFamily = "'Fusion Pixel', 'Courier New', monospace";
  document.body.appendChild(measurer);

  for (let i = 0; i < numColumns; i++) {
    let maxContentWidth = 0;
    measurer.textContent = visibleHeader.value[i];
    maxContentWidth = measurer.getBoundingClientRect().width;

    // 列宽按"全表所有行"测量(不受筛选影响):开/关筛选时列宽保持不变,排版稳定
    for (const fullRow of (props.tableData.rows || [])) {
      if (!Array.isArray(fullRow) || fullRow.length === 0) continue
      const row = fullRow.slice(0, -1)
      if (row[i] != null) {
        measurer.textContent = row[i];
        const contentWidth = measurer.getBoundingClientRect().width;
        if (contentWidth > maxContentWidth) {
          maxContentWidth = contentWidth;
        }
      }
    }

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

// === 终端式整行显示 ===
// 1) 容器可视高度对齐行网格(向下取整,窗口初始化/变化时计算)
// 2) 滚动位置吸附到行网格(行顶边贴住表头下沿)
// 两者配合才能保证任何时刻画面里只有完整行
const headerSnapTop = () => {
  // 用粘性 th 本身的几何:sticky top + th 实测高度。
  // 不要用 thead.offsetHeight(含边距陷阱,会偏 4px 导致整个网格错位)
  const thead = headerRef.value;
  const th = thead && thead.querySelector('th');
  if (!th) return 40;
  const top = parseFloat(getComputedStyle(th).top);
  return (isNaN(top) ? 16 : top) + th.offsetHeight;
};

const rowStride = () => {
  const r0 = rowRefs.value[0];
  const r1 = rowRefs.value[1];
  if (r0 && r1) return r1.offsetTop - r0.offsetTop;
  return r0 ? r0.offsetHeight + 6 : 38;
};

let fittedVisibleRows = 0   // fitVisibleRows 测得的可完整显示行数(唯一事实来源)
const fittedHeight = ref(0) // 拟合后的滚动区高度(供底线显示判断)
const emptyFillHeight = ref(0) // 不足一页时末行到底线的"空行"填充高度

const fitVisibleRows = () => {
  const container = scrollContainerRef.value;
  const parent = container && container.parentElement;
  if (!container || !parent) return;
  // 从父容器推算自然可用高度(不动自身 height,避免测量-还原引发
  // ResizeObserver 振荡循环)
  const pcs = getComputedStyle(parent);
  const natural = parent.clientHeight
    - parseFloat(pcs.paddingTop || '0')
    - parseFloat(pcs.paddingBottom || '0');
  const stride = rowStride();
  const top = headerSnapTop();
  if (stride <= 0 || natural <= top) return;
  const rows = Math.max(1, Math.floor((natural - top) / stride));
  fittedVisibleRows = rows;
  // 高度落在"第 n 行底边 ~ 第 n+1 行顶边"的间隙中间:
  // n 行完整显示,第 n+1 行一个像素都不进入视野
  const desired = Math.round(top + rows * stride - 3);
  fittedHeight.value = desired;
  if (Math.abs(container.clientHeight - desired) >= 1) {
    container.style.height = desired + 'px';
  }
  // 不足一页的表格:末行到底线之间补一段"空行"填充。
  // 除垫满一页外,还要再多垫出网格基准偏移(base):不足一页时若
  // scrollHeight == clientHeight,scrollTop 会被钳在 0,吸附点
  // base(行贴齐表头所需)滚不到 → 表头脱钉、行与表头露出缝隙,
  // 视觉上"回退到原效果"。多垫的部分在视口下方,被裁掉不可见。
  // 注意:筛选到 0 行时也要垫(gridBase() 会用表头几何兜底),
  // 否则表头同样会脱钉、看着整体下移
  const table = container.querySelector('table');
  if (table) {
    const basePad = Math.max(0, gridBase());
    emptyFillHeight.value = Math.max(0, desired + basePad - table.offsetHeight);
  }
};

// 行在"容器内容坐标"中的位置(offsetTop 对表格内部元素是相对 table 的,
// 与容器坐标恒差一个表头偏移 —— 必须统一用 rect 换算)
const rowTopInContent = (rowEl) => {
  const container = scrollContainerRef.value;
  if (!container || !rowEl) return 0;
  return rowEl.getBoundingClientRect().top
    - container.getBoundingClientRect().top
    + container.scrollTop;
};

// 行网格基准:首行顶边贴住表头下沿时的 scrollTop(= 首行在内容坐标里的位置 - 表头钉住后的下沿)。
// 没有可显示的行(例如筛选后 0 行)时用表格/表头几何推算首行本该出现的位置 ——
// 否则 scrollTop 会停在 0,表头回到自然位置(border-top + border-spacing,比钉住时低 ~8px),
// 视觉上就是"点完表头整行表头往下跳"
const gridBase = () => {
  const container = scrollContainerRef.value;
  if (!container) return 0;
  const r0 = rowRefs.value[0];
  if (r0) return rowTopInContent(r0) - headerSnapTop();
  const table = container.querySelector('table');
  const th = headerRef.value ? headerRef.value.querySelector('th') : null;
  if (!table || !th) return 0;
  const cs = getComputedStyle(table);
  const borderTop = parseFloat(cs.borderTopWidth) || 0;
  const parts = String(cs.borderSpacing || '0px').trim().split(/\s+/);
  const spacingY = parseFloat(parts[1] !== undefined ? parts[1] : parts[0]) || 0;
  const rowStart = rowTopInContent(table) + borderTop + spacingY + th.offsetHeight + spacingY;
  return rowStart - headerSnapTop();
};

const snapScroll = (target) => {
  const container = scrollContainerRef.value;
  if (!container) return Math.max(0, target || 0);
  const stride = rowStride();
  // 网格基准:第 0 行顶边贴住表头下沿时的 scrollTop
  const base = gridBase();
  const rows = rowRefs.value.length;
  // 用 fitVisibleRows 的拟合结果(与高度拟合同源);用容器高度重算会
  // 因间隙扣减向下取整少一行,导致钳制上限越过 rawMax、吸附失效
  const visibleRows = fittedVisibleRows
    || Math.max(1, Math.floor((container.clientHeight - headerSnapTop()) / stride));
  const rawMax = container.scrollHeight - container.clientHeight;
  // 钳制上限也网格化:最后一行恰好完整贴底。
  // 直接用 rawMax 会把吸附点拽离网格,顶部行就被表头切掉一截
  const gridMax = base + Math.max(0, rows - visibleRows) * stride;
  // k 夹取到 [0, kMax]:负的居中目标落在 k=0(首屏顶格 S=base),
  // 而不是被外层钳制拽回 S=0 —— 那会让表头脱离钉住位置、行不贴齐
  const kMax = Math.max(0, rows - visibleRows);
  const k = Math.min(kMax, Math.max(0, Math.round(((target || 0) - base) / stride)));
  const snapped = base + k * stride;
  return Math.max(0, Math.min(rawMax, Math.min(gridMax, snapped)));
};

// 吸附到网格基准位(首行贴住表头下沿)。
// 注意要等"空行填充"的高度落进 DOM 再吸附:填充高度是响应式的,写晚了
// 滚动区还只有几行高,scrollTop 会被钳到 0 —— 表头随之不再被 sticky 钉住,
// 视觉上整行表头下移 ~8px(border-spacing + border-top 的自然位置)
const snapToGridTop = async () => {
  await nextTick();
  const container = scrollContainerRef.value;
  if (!container) return;
  container.scrollTop = snapScroll(0);
  await nextTick();
};

const scrollSelectionIntoView = () => {
  const container = scrollContainerRef.value;
  const rowElement = rowRefs.value[selectedRowIndex.value];

  if (!container || !rowElement) return;

  // 选中行滚动到可视区中央附近,再吸附到最近的行网格点;
  // 到达顶部/底部时被自然钳制,选中行随之继续上移/下移
  const rowCenter = rowTopInContent(rowElement) + rowElement.offsetHeight / 2;
  const target = rowCenter - container.clientHeight / 2;
  const newScrollTop = snapScroll(target);

  if (Math.abs(newScrollTop - container.scrollTop) > 1) {
    container.scrollTop = newScrollTop;
  }
};

watch(selectedRowIndex, () => {
  keyboardGlow.light(selectedRowIndex.value);
  scrollSelectionIntoView();
}, { flush: 'post' });

// 筛选开/关:显示行数变了,清掉旧的行引用并重新拟合整行网格、光标回到首行
watch(() => props.filterIndexes, async () => {
  rowRefs.value = [];
  selectedRowIndex.value = 0;
  clickLitIndex.value = -1;
  await nextTick();
  calculateColumnWidths();
  updateHeaderHeight();
  fitVisibleRows();
  keyboardGlow.light(0);
  await snapToGridTop();
}, { deep: true });


onMounted(() => {
  nextTick(() => {
    updateHeaderHeight();
    // 初始化时计算一轮可用行数,容器高度向下取整到整行
    fitVisibleRows();
    // 初始也吸附到行网格,首屏即只有完整行(短表格要等空行填充落定后再吸附)
    snapToGridTop();
    scrollContainerRef.value?.focus();
    // 初始选中行也点亮,静置后同样渐隐
    keyboardGlow.light(selectedRowIndex.value);
  });

  // 像素字体异步加载完成后表头高度会变,挂载时测的几何是过期的,
  // 字体就绪后必须重算一轮并重新对齐
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => {
      updateHeaderHeight();
      fitVisibleRows();
      scrollSelectionIntoView();
    });
  }

  window.addEventListener('keydown', handleKeydown);

  const resizeObserver = new ResizeObserver(() => {
    calculateColumnWidths();
    updateHeaderHeight();
    // 窗口尺寸变化:重算可用行数并保持网格对齐
    fitVisibleRows();
    scrollSelectionIntoView();
  });
  
  if (scrollContainerRef.value) {
    resizeObserver.observe(scrollContainerRef.value);
  }

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
    resizeObserver.disconnect();
    keyboardGlow.dispose();
    clickGlow.dispose();
  });
})

const visibleHeader = computed(() => {
  if (!props.tableData.header) return [];
  return props.tableData.header.slice(0, -1);
});

const visibleRows = computed(() => {
  const rows = props.tableData.rows || [];
  return displayIndexes.value.map(i => {
    const row = rows[i];
    if (Array.isArray(row) && row.length > 0) {
      return row.slice(0, -1);
    }
    return row;
  });
});

const progressColumnIndex = computed(() => props.tableData.header.length - 1)

// 以下 rowIndex 一律是"显示下标"(见 displayIndexes)
const isRowCompleted = (rowIndex) => {
  if (progressColumnIndex.value === -1) return false
  const row = rowAt(rowIndex)
  return row && row[progressColumnIndex.value] === '[x]'
}
const isSeparatorRow = (rowIndex) => {
  const row = rowAt(rowIndex)
  return row === null || row === undefined || (Array.isArray(row) && row.length === 0)
}
const toggleRowCompletion = (rowIndex) => {
  if (progressColumnIndex.value === -1) return
  
  const row = rowAt(rowIndex)
  if (!row || row.length === 0) return
  
  row[progressColumnIndex.value] = row[progressColumnIndex.value] === '[x]' ? '[ ]' : '[x]'
  
  emit('update', {
    rows: [...props.tableData.rows]
  })
}
const handleRowClick = (rowIndex) => {
  if (isSeparatorRow(rowIndex)) return

  // 鼠标点击:只切换这一行的状态 + 点亮它,不移动键盘光标。
  // 键盘光标不动 => 不触发 scrollSelectionIntoView => 画面不会跟着跳
  clickLitIndex.value = rowIndex
  clickGlow.light(rowIndex)
  toggleRowCompletion(rowIndex)
}

// 点击表头:开/关筛选。开启时把"此刻未完成的行"冻结成下标数组交给父组件保存
// (状态挂在上层,切换表格再回来仍然是同一批行;退出文件才清空)
const toggleFilter = () => {
  if (isFiltered.value) {
    emit('toggle-filter', null)
    return
  }
  const rows = props.tableData.rows || []
  const frozen = []
  rows.forEach((row, i) => {
    if (!Array.isArray(row) || row.length === 0) return        // 分隔行不算任务
    if (row[progressColumnIndex.value] !== '[x]') frozen.push(i)
  })
  emit('toggle-filter', frozen)
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
  const count = displayIndexes.value.length
  let newIndex = selectedRowIndex.value + 1
  while (newIndex < count && isSeparatorRow(newIndex)) {
    newIndex++
  }
  if (newIndex < count) {
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
  padding-bottom: var(--crt-frame-bottom);
  box-sizing: border-box;
  position: relative;
  /* 纵向 flex:滚动区(已拟合整行) + 空隙填充 + 底部横线,
     横线被推到容器内容区底边 —— 与文件树/表格列表页的横线同一条线 */
  display: flex;
  flex-direction: column;
}

/* 底部横线:文档流块元素,天然紧贴滚动区底边(滚动区高度已拟合,
   线就在最后一个完整行下方);左右 margin 与列表列宽对齐 */
.table-bottom-line {
  flex: none;
  height: 1px;
  margin: 0 var(--crt-spacing-xl);
  background: var(--crt-border);
}

/* 拟合留下的空隙:左右边框与列网格同宽,内部无分隔线 */
.table-frame-fill {
  flex: 1 1 auto;
  min-height: 0;
  margin: 0 var(--crt-spacing-xl);
  border-left: 1px solid var(--crt-border);
  border-right: 1px solid var(--crt-border);
  box-sizing: border-box;
}

/* 筛选后没有剩余未完成项时的提示(挂在空行填充区顶部,表头正下方) */
.table-filter-empty {
  padding-top: var(--crt-spacing-lg);
  text-align: center;
  font-size: var(--crt-font-size-xs);
  color: var(--crt-text-dim);
  letter-spacing: 2px;
  text-shadow: 0 0 var(--crt-glow-strength) var(--crt-glow-color);
}

/* 不足一页的表格:末行与底线之间的空隙,以"空行"呈现 ——
   只保留左右边框(与列网格同宽),内部无分隔线 */
.table-empty-fill {
  border-left: 1px solid var(--crt-border);
  border-right: 1px solid var(--crt-border);
  box-sizing: border-box;
}

.table-view {
  flex: none;
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
  /* +4px:把行网格起点对齐到粘性表头下沿(16px + 表头高),
    这样 scrollTop=0 和所有吸附点都是整行边界 */
  border-top: 4px solid transparent;
}

thead {
  background-color: transparent;
}

th {
  position: sticky;
  top: 2px;
  z-index: 10;
  background: var(--crt-bg);
  color: var(--crt-text);
  border: none;
  border-bottom: 1px solid var(--crt-border);
  /* 与数据列对齐:每列都有左分隔线(td 同款),列间竖线贯通表头与内容 */
  border-left: 1px solid var(--crt-border);
  font-size: var(--crt-font-size-xs);
  padding: var(--crt-spacing-sm) var(--crt-spacing-sm);
  text-transform: uppercase;
  text-align: center;
  letter-spacing: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  box-sizing: border-box;
  cursor: pointer;
  /* 扫描线上的荧光粉效果 */
  text-shadow: 0 0 var(--crt-glow-strength) var(--crt-glow-color);
  /* 粘性表头阴影:盖住 sticky top 上方滚过的内容。
     不设 border-top:表头紧贴顶栏底线(2px),顶栏线即框架顶线,
     再画一条会视觉上出现"双线" */
  box-shadow: 0 -2px 0 0 var(--crt-bg);
}

/* 筛选模式:表头文字变强调色,提示"现在只看未完成"
   (只改文字颜色,边框/尺寸不动 —— 避免表头看着"跳"一下) */
.table-view.filtered th {
  color: var(--crt-accent);
  text-shadow: 0 0 var(--crt-glow-strength) var(--crt-accent);
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

/* 全局 main.css 的 .highlight 会给 tr 本体刷半透明背景,
   熄灭态 td 透明后这层底色会透出来;必须在 tr 层一并清掉 */
tr.highlight {
  background-color: transparent !important;
}

/* 点亮/熄灭由 --sel-alpha 驱动(0~1,JS 逐帧写入行内样式),
   颜色取自方案 highlight_strong 解析出的 --crt-select-rgb/--crt-select-max,
   快照因此能看到完整渐隐过程,且随配色方案换色 */
tr.highlight td {
  background-color: rgba(var(--crt-select-rgb, 255, 255, 255), calc(var(--sel-alpha, 0) * var(--crt-select-max, 0.15))) !important;
  box-shadow: inset 0 0 4px rgba(var(--crt-select-rgb, 255, 255, 255), calc(var(--sel-alpha, 0) * var(--crt-select-max, 0.15) * 0.2));
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
  /* 与数据行同高:统一行网格,才能实现"只显示完整行"的终端式对齐 */
  height: 32px;
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
