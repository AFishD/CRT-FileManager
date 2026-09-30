<template>
  <div class="crt-monitor">
    <!-- CRT显示器外壳 -->
    <div class="crt-bezel">
      <!-- CRT屏幕玻璃:真实 DOM(可交互但不可见)+ WebGL 合成画面 -->
      <div class="crt-screen" ref="screenRef">
        <!-- 内容层:opacity:0 但仍参与命中测试,点击/滚轮/键盘全部有效 -->
        <div
          class="crt-content"
          ref="contentRef"
          :class="{ 'crt-hidden': hideContent }"
        >
          <slot></slot>
        </div>

        <!-- WebGL 画面层:指针事件穿透到下面的真实 DOM -->
        <canvas ref="canvasRef" class="crt-canvas" v-show="rendererActive"></canvas>
      </div>
    </div>

    <!-- 电源指示灯 -->
    <div v-if="powerLedEnabled" class="crt-power-led" :class="{ 'on': effectsEnabled }"></div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { prepareSnapshot, renderSnapshot } from '../crt/rasterizer.js'
import { CRTRenderer } from '../crt/renderer.js'

const props = defineProps({
  config: {
    type: Object,
    required: true
  }
})

const screenRef = ref(null)
const contentRef = ref(null)
const canvasRef = ref(null)

const effectsEnabled = computed(() => props.config?.crt_effects?.enabled ?? true)
const powerLedEnabled = computed(() => props.config?.crt_effects?.power_led?.enabled ?? true)

const rendererActive = ref(false)  // canvas 是否在显示
const hideContent = ref(false)     // 真实 DOM 是否已隐藏(首帧成功后)

let renderer = null
let workCanvas = null       // 栅格化专用离屏 canvas
let rafId = 0
let disposed = false

// 快照调度
let dirty = true           // 内容变化,需要重新栅格化
let snapshotPending = false
let lastSnapAt = 0
let minSnapInterval = 66   // 自适应:按上次快照耗时动态放宽

let mutationObserver = null
let resizeObserver = null
let cssW = 0
let cssH = 0
let dpr = 1
let dirtyUntil = 0   // 此时间点之前持续补拍快照(覆盖 CSS 过渡动画)
let latestParams = { barrelX: 0.18, barrelY: 0.22, zoom: 1.02 }  // 供指针坐标反算

// ── 指针坐标反算:屏幕坐标 → 内容坐标 ───────────────────────────────────────
// 与 shaders.js 的顶点映射完全同构(zoom → crtPiCurve → 边缘补偿),
// 视觉上内容被弯曲到哪里,点击就落到哪里 —— 命中区跟随桶形畸变
function screenToContent(clientX, clientY) {
  const canvas = canvasRef.value
  if (!canvas) return null
  const rect = canvas.getBoundingClientRect()
  if (!rect.width || !rect.height) return null
  const u = (clientX - rect.left) / rect.width
  const v = (clientY - rect.top) / rect.height
  const p = latestParams
  const zoom = Math.max(p.zoom, 0.001)
  const zx = (u - 0.5) / zoom + 0.5
  const zy = (v - 0.5) / zoom + 0.5

  const curve = (x, y) => {
    const kx = p.barrelX * 5
    const ky = p.barrelY * 5
    let a = x - 0.5
    let b = y - 0.5
    const rsq = a * a + b * b
    a += a * (kx * rsq)
    b += b * (ky * rsq)
    a *= 1 - 0.23 * kx
    b *= 1 - 0.23 * ky
    return [a + 0.5, b + 0.5]
  }
  const [cx0, cy0] = curve(zx, zy)
  const rightX = curve(1, 0.5)[0] - 0.5
  const bottomY = curve(0.5, 1)[1] - 0.5
  const cx = (cx0 - 0.5) * (0.5 / Math.max(Math.abs(rightX), 1e-5)) + 0.5
  const cy = (cy0 - 0.5) * (0.5 / Math.max(Math.abs(bottomY), 1e-5)) + 0.5

  if (cx < 0 || cx > 1 || cy < 0 || cy > 1) return null   // 玻璃边框黑区
  return { x: rect.left + cx * rect.width, y: rect.top + cy * rect.height }
}

function contentTargetAt(clientX, clientY) {
  const pt = screenToContent(clientX, clientY)
  if (!pt) return null
  // elementFromPoint 会命中最顶层的 canvas 自己 —— 查询瞬间
  // 临时关掉 canvas 的命中测试,让它返回下方的内容元素
  const canvas = canvasRef.value
  const prevPE = canvas.style.pointerEvents
  canvas.style.pointerEvents = 'none'
  let el = null
  try {
    el = document.elementFromPoint(pt.x, pt.y)
  } finally {
    canvas.style.pointerEvents = prevPE
  }
  if (!el || !contentRef.value || !contentRef.value.contains(el)) return null

  // 遮挡检测:滚动容器内、粘性表头底边之上的区域,内容被表头
  // (或其 16px 覆盖阴影)挡住 —— box-shadow 只参与绘制不参与命中,
  // 滚过表头的行在那里仍然可被 elementFromPoint 命中,
  // 造成"看不见却能点到下方行"的泄漏,一律视为不可交互
  const scrollHost = el.closest ? el.closest('.table-view') : null
  if (scrollHost && scrollHost !== el) {
    const th = scrollHost.querySelector('thead th')
    if (th && !th.contains(el)) {
      const thBottom = th.getBoundingClientRect().bottom
      const hostTop = scrollHost.getBoundingClientRect().top
      if (pt.y < thBottom && pt.y >= hostTop) return null
    }
  }
  return el
}

// 悬停态显式标记(canvas 拦截后真实 DOM 不会进入 :hover,
// 栅格化器会读取 __crt_hover 类,快照 CSS 也已把 :hover 改写成该类)
let hoverChain = []
function setHoverChain(target) {
  const chain = []
  let el = target
  const root = contentRef.value
  while (el && el !== root) { chain.push(el); el = el.parentElement }
  for (const el of hoverChain) {
    if (!chain.includes(el)) el.classList.remove('__crt_hover')
  }
  for (const el of chain) {
    if (!hoverChain.includes(el)) el.classList.add('__crt_hover')
  }
  hoverChain = chain
}

function onCanvasPointerMove(e) {
  let target = contentTargetAt(e.clientX, e.clientY)
  // 表头是界面 chrome 而非内容:悬停表头不产生任何高亮。
  // 否则表头与首行边界处,行背景随鼠标快速亮灭,视觉上
  // 表头列分隔区域出现"部分显示/部分隐藏"的闪烁
  if (target && target.closest && target.closest('thead')) target = null
  setHoverChain(target)
  if (canvasRef.value) {
    canvasRef.value.style.cursor = target ? (getComputedStyle(target).cursor || 'default') : 'default'
  }
}

function onCanvasPointerLeave() {
  setHoverChain(null)
  if (canvasRef.value) canvasRef.value.style.cursor = 'default'
}

function onCanvasClick(e) {
  const target = contentTargetAt(e.clientX, e.clientY)
  if (!target) return
  target.dispatchEvent(new MouseEvent('click', {
    bubbles: true, cancelable: true,
    clientX: e.clientX, clientY: e.clientY
  }))
  // 合成事件不会触发浏览器原生聚焦,手动补
  const focusable = target.closest('[tabindex],button,a,input,select,textarea')
  if (focusable) focusable.focus({ preventScroll: true })
}

function onCanvasWheel(e) {
  const target = contentTargetAt(e.clientX, e.clientY)
  if (!target) return
  const ev = new WheelEvent('wheel', {
    bubbles: true, cancelable: true,
    clientX: e.clientX, clientY: e.clientY,
    deltaX: e.deltaX, deltaY: e.deltaY
  })
  const notPrevented = target.dispatchEvent(ev)
  if (notPrevented) {
    // 合成滚轮不会触发原生滚动:对没有自身处理器的可滚动祖先手动滚
    let el = target
    while (el && el !== document.body) {
      if (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1) {
        const cs = getComputedStyle(el)
        if (/(auto|scroll)/.test(cs.overflowY + cs.overflow)) {
          el.scrollTop += e.deltaY
          el.scrollLeft += e.deltaX
          break
        }
      }
      el = el.parentElement
    }
  }
}

// ── 配置 → 渲染参数(兼容旧字段) ──────────────────────────────────────────
function computeRendererParams() {
  const e = props.config?.crt_effects ?? {}
  const d = e.distortion ?? {}
  const s = e.scanlines ?? {}
  const m = e.shadow_mask ?? {}
  const v = e.vignette ?? {}
  const g = e.glow ?? {}
  const f = e.flicker ?? {}
  const blur = e.blur ?? {}

  // barrel_x/barrel_y 是新字段;旧配置只有 distortion.strength(原遮罩收缩强度),
  // 语义换算后继续当畸变强度用
  const barrelFallback = d.strength ?? 0.12
  const barrelX = d.barrel_x ?? barrelFallback
  const barrelY = d.barrel_y ?? barrelFallback

  const spacing = Math.max(1, s.spacing ?? 2)
  const scanCount = Math.max(1, cssH / spacing)

  // glow.strength 原本是给 CSS text-shadow 用的(那层已烘焙进快照),
  // 着色器这层 bloom 只做补充,系数压低避免双重辉光过曝
  const glowPx = parseFloat(g.strength) || 1
  const blurPx = parseFloat(blur.strength) || 0
  const glowAmount = Math.min(1, glowPx / 14 + blurPx / 8)

  const cornerPx = d.corner_radius ?? 16

  return {
    barrelX: Math.max(0, Math.min(0.4, barrelX)),
    barrelY: Math.max(0, Math.min(0.4, barrelY)),
    zoom: d.zoom ?? 1.02,
    scanOpacity: Math.max(0, Math.min(1, s.opacity ?? 0.3)),
    scanCount,
    maskOpacity: (m.enabled ?? true) ? Math.max(0, Math.min(1, m.opacity ?? 0.06)) : 0,
    vignette: Math.max(0, Math.min(1, v.strength ?? 0.5)),
    glow: glowAmount,
    flicker: (f.enabled ?? true) ? Math.max(0, Math.min(0.5, f.intensity ?? 0.03)) : 0,
    persistence: Math.max(0, Math.min(0.95, e.persistence ?? 0.25)),
    corner: Math.max(0, Math.min(0.45, cornerPx / Math.max(1, cssH))),
    cornerSharp: 600
  }
}

function applyParams() {
  if (!renderer) return
  const params = computeRendererParams()
  renderer.setParameters(params)
  latestParams = { barrelX: params.barrelX, barrelY: params.barrelY, zoom: params.zoom }
  // glow/闪烁等属于着色器效果,参数变化即时生效,无需重新栅格化
}

function markDirty() {
  dirty = true
  // 覆盖 CSS 过渡动画期:渐隐/渐显这类动画不产生 DOM 变更,
  // 若只在变更瞬间拍一帧,画面会冻结在动画起始帧
  dirtyUntil = performance.now() + 1200
}

// ── 尺寸 ───────────────────────────────────────────────────────────────────
function measure() {
  const el = contentRef.value
  if (!el) return false
  const w = el.clientWidth
  const h = el.clientHeight
  if (!w || !h) return false
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  if (w !== cssW || h !== cssH) {
    cssW = w
    cssH = h
    if (renderer) renderer.resize(cssW, cssH, dpr)
    applyParams()
  }
  return true
}

// ── 快照:DOM → 纹理 ───────────────────────────────────────────────────────
async function takeSnapshot() {
  if (!renderer || !contentRef.value) return
  if (!measure()) return

  // prepareSnapshot 会短暂修改真实 DOM(打标记),期间暂停观察器避免自我触发
  mutationObserver?.disconnect()
  let prep
  try {
    prep = prepareSnapshot(contentRef.value)
  } finally {
    if (mutationObserver && !disposed) {
      mutationObserver.observe(contentRef.value, { subtree: true, childList: true, attributes: true, characterData: true })
    }
  }

  const t0 = performance.now()
  await renderSnapshot(prep, workCanvas)
  const dur = performance.now() - t0
  // 快照耗时自适应节流:交互期间尽量跟上,上限收紧以降低滚动迟滞
  minSnapInterval = Math.max(50, Math.min(160, Math.round(dur * 1.1)))

  renderer.uploadContent(workCanvas)
  if (!hideContent.value) hideContent.value = true
}

// ── 主循环 ─────────────────────────────────────────────────────────────────
function tick() {
  if (disposed) return
  rafId = requestAnimationFrame(tick)

  const now = performance.now()
  if ((dirty || now < dirtyUntil) && !snapshotPending && now - lastSnapAt >= minSnapInterval) {
    dirty = false
    snapshotPending = true
    lastSnapAt = now
    takeSnapshot()
      .catch((err) => {
        const detail = err && (err.stack || (err.name + ': ' + err.message) || String(err))
        console.warn('[CRT] snapshot failed, falling back to plain DOM:', detail)
        degrade()
      })
      .finally(() => {
        snapshotPending = false
      })
  }

  renderer?.render(now / 1000)
}

// 降级:隐藏 WebGL,直接显示真实 DOM(无畸变)
function degrade() {
  rendererActive.value = false
  hideContent.value = false
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  teardownObservers()
  renderer?.dispose()
  renderer = null
  if (canvasRef.value) canvasRef.value.style.display = 'none'
}

function teardownObservers() {
  mutationObserver?.disconnect()
  mutationObserver = null
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('scroll', onScrollCapture, true)
  window.removeEventListener('resize', markDirty)
  window.removeEventListener('pointermove', markDirty)
  if (canvasRef.value) {
    canvasRef.value.removeEventListener('pointermove', onCanvasPointerMove)
    canvasRef.value.removeEventListener('pointerleave', onCanvasPointerLeave)
    canvasRef.value.removeEventListener('click', onCanvasClick)
    canvasRef.value.removeEventListener('wheel', onCanvasWheel)
  }
  setHoverChain(null)
}

function onScrollCapture() {
  markDirty()
}

// ── 生命周期 ───────────────────────────────────────────────────────────────
function setup() {
  try {
    renderer = new CRTRenderer(canvasRef.value)
  } catch (err) {
    console.warn('[CRT] WebGL2 unavailable, plain DOM mode:', err)
    return false
  }

  workCanvas = document.createElement('canvas')

  measure()
  renderer.resize(cssW || 1, cssH || 1, dpr)
  applyParams()

  mutationObserver = new MutationObserver(markDirty)
  mutationObserver.observe(contentRef.value, { subtree: true, childList: true, attributes: true, characterData: true })

  // scroll 事件不冒泡,capture 阶段在 window 上截获所有容器滚动
  window.addEventListener('scroll', onScrollCapture, { capture: true, passive: true })
  window.addEventListener('resize', markDirty)
  // 悬停态是纯 CSS 伪类,不产生 DOM 变更;鼠标移动也要触发快照,
  // 否则行悬停高亮只在滚动时才顺带刷新
  window.addEventListener('pointermove', markDirty, { passive: true })

  // 指针接管:canvas 截获全部指针事件,坐标经畸变反算后转发给
  // 真实 DOM —— 命中区与视觉上的弯曲分区一致
  if (canvasRef.value) {
    canvasRef.value.addEventListener('pointermove', onCanvasPointerMove, { passive: true })
    canvasRef.value.addEventListener('pointerleave', onCanvasPointerLeave)
    canvasRef.value.addEventListener('click', onCanvasClick)
    canvasRef.value.addEventListener('wheel', onCanvasWheel, { passive: true })
  }

  resizeObserver = new ResizeObserver(() => {
    if (measure()) markDirty()
  })
  resizeObserver.observe(contentRef.value)

  rendererActive.value = true
  hideContent.value = true   // 开机黑屏,首帧快照完成后由 canvas 接管画面

  dirty = true
  rafId = requestAnimationFrame(tick)
  return true
}

onMounted(async () => {
  await nextTick()
  if (!effectsEnabled.value) return
  if (!setup()) {
    hideContent.value = false
  }
})

onBeforeUnmount(() => {
  disposed = true
  if (rafId) cancelAnimationFrame(rafId)
  teardownObservers()
  renderer?.dispose()
  renderer = null
})

// 配置热更新(API 拉到 / 用户改配置):参数即时下发;内容层样式
// (text-shadow 等)变了也要重新栅格化
watch(() => props.config, () => {
  applyParams()
  markDirty()
}, { deep: true })

watch(effectsEnabled, (on) => {
  if (!on && renderer) degrade()
})
</script>

<style scoped>
/* === 显示器外壳 === */
.crt-monitor {
  width: 100vw;
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
  background: #1a1a1a;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

/* === 显示器边框 === */
.crt-bezel {
  width: 100%;
  height: 100%;
  position: relative;
  padding: 12px;
  box-sizing: border-box;
  background: #0a0a0a;
  box-shadow:
    inset 0 0 60px rgba(0, 0, 0, 0.8),
    inset 0 0 3px rgba(255, 255, 255, 0.03);
}

/* === CRT屏幕 === */
.crt-screen {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: #000000;
}

/* === 内容层:不可见但可交互 === */
.crt-content {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;
  user-select: none;
}

.crt-content.crt-hidden {
  opacity: 0;
}

/* === WebGL 画面层:接管指针事件,坐标经畸变反算后转发给真实 DOM === */
.crt-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
  pointer-events: auto;
}

/* === 电源指示灯 === */
.crt-power-led {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #333;
  position: absolute;
  bottom: 6px;
  right: 24px;
  z-index: 10;
  transition: all 0.5s ease;
}

.crt-power-led.on {
  background: #00ff00;
  box-shadow:
    0 0 4px #00ff00,
    0 0 8px #00ff00,
    0 0 16px rgba(0, 255, 0, 0.4);
}
</style>
