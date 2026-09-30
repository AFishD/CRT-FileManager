/**
 * DOM → Canvas 栅格化器
 *
 * 把一块真实 DOM(含样式、字体、滚动位置、hover 状态)拍成一张 canvas,
 * 供 WebGL CRT 着色器当作纹理采样。实现方式是 SVG foreignObject:
 *
 *   clone(DOM) + 内联全部 CSS(字体转 data URL) → 序列化成 SVG → <img> 解码 → 画到 canvas
 *
 * 之所以手写而不用 html2canvas 之类:我们需要对克隆树做三类定制修正,
 * 第三方库没有暴露钩子:
 *   1. 滚动补偿 —— foreignObject 里布局从 scrollTop=0 开始,不会保留滚动位置;
 *      这里把滚动容器设为 overflow:hidden 并平移其直接子元素。
 *   2. 粘性元素 —— position:sticky 在未滚动的克隆里不会"钉住"。对当前确实
 *      处于钉住状态的 sticky 元素:克隆一份隐藏占位符保住布局槽位,本体改为
 *      绝对定位钉在它当前渲染的位置。
 *   3. 交互态复刻 —— :hover / :focus 在图片上下文里永远不成立。收集样式表时
 *      把这两个伪类改写成 .__crt_hover / .__crt_focus 类,再给克隆树里对应的
 *      元素打上类。
 *
 * 字体内联只处理"页面文本实际可能用到"的 @font-face(按 unicode-range 判断),
 * 避免把整套 CJK 字体(每个 ~700KB)全部塞进快照。
 */

const XHTML_NS = 'http://www.w3.org/1999/xhtml'
const MARK_ATTR = 'data-crt-snap'
const DPR_CAP = 2

// ── 字体/资源抓取缓存(url → Promise<dataURL>) ────────────────────────────
const dataUrlCache = new Map()

function fetchAsDataUrl(url) {
  if (dataUrlCache.has(url)) return dataUrlCache.get(url)
  const p = (async () => {
    const res = await fetch(url)
    if (!res.ok) throw new Error('resource fetch failed: ' + url)
    const blob = await res.blob()
    let dataUrl = await new Promise((resolve, reject) => {
      const fr = new FileReader()
      fr.onload = () => resolve(fr.result)
      fr.onerror = () => reject(fr.error || new Error('readAsDataURL failed'))
      fr.readAsDataURL(blob)
    })
    // 服务器对 woff2 可能返回错误的 Content-Type(如 text/plain),
    // data URL 的 MIME 会原样进入 @font-face src,浏览器会拒绝非字体 MIME。
    // 按扩展名修正
    if (/\.woff2?($|\?)/i.test(url) && /^data:(text|application)\/[a-z.+-]+;/i.test(dataUrl)) {
      dataUrl = dataUrl.replace(/^data:[^;]+;/, /\.woff($|\?)/i.test(url) ? 'data:font/woff;' : 'data:font/woff2;')
    }
    return dataUrl
  })()
  dataUrlCache.set(url, p)
  p.catch(() => dataUrlCache.delete(url))
  return p
}

// ── unicode-range 解析(判断某个 @font-face 是否覆盖页面用到的字符) ──────
function parseUnicodeRange(str) {
  const ranges = []
  for (const token of str.split(',')) {
    const t = token.trim().replace(/^u\+/i, '')
    if (!t) continue
    if (t.includes('-')) {
      const [a, b] = t.split('-')
      ranges.push([parseInt(a, 16), parseInt(b, 16)])
    } else if (t.includes('?')) {
      ranges.push([parseInt(t.replace(/\?/g, '0'), 16), parseInt(t.replace(/\?/g, 'F'), 16)])
    } else {
      const v = parseInt(t, 16)
      if (!isNaN(v)) ranges.push([v, v])
    }
  }
  return ranges
}

function faceCoversChars(rangeText, codes) {
  const ranges = parseUnicodeRange(rangeText)
  if (!ranges.length) return true
  for (const code of codes) {
    for (const [lo, hi] of ranges) {
      if (code >= lo && code <= hi) return true
    }
  }
  return false
}

// ── 样式表收集与改写 ────────────────────────────────────────────────────────

// 快照上下文里 :root/html/body 都不存在,改写成类;:hover/:focus 同理
function rewriteSelector(sel) {
  return sel
    .replace(/(^|[\s,>+~])html\b/gi, '$1.__crt_root')
    .replace(/(^|[\s,>+~])body\b/gi, '$1.__crt_body')
    .replace(/:root/gi, ':root, .__crt_root')
    .replace(/:focus-visible/gi, '.__crt_focus')
    .replace(/:focus/gi, '.__crt_focus')
    .replace(/:hover/gi, '.__crt_hover')
}

// vh/vw 依赖 SVG 视口尺寸(会被 dpr 放大),换成绝对 px
function viewportUnitsToPx(text, cssW, cssH) {
  return text
    .replace(/(\d*\.?\d+)vw/gi, (m, v) => (parseFloat(v) / 100) * cssW + 'px')
    .replace(/(\d*\.?\d+)vh/gi, (m, v) => (parseFloat(v) / 100) * cssH + 'px')
}

const URL_RE = /url\(\s*(['"]?)([^'")]+)\1\s*\)/g

function collectRuleEntries(entries, rules, baseUrl) {
  for (const rule of rules) {
    if (rule instanceof CSSMediaRule || rule instanceof CSSSupportsRule) {
      const children = []
      collectRuleEntries(children, rule.cssRules, baseUrl)
      const prefix =
        rule instanceof CSSMediaRule
          ? '@media ' + rule.conditionText
          : '@supports ' + rule.conditionText
      entries.push({ kind: 'block', prefix, children })
    } else if (rule instanceof CSSFontFaceRule) {
      entries.push({ kind: 'font', rule, baseUrl })
    } else if (rule instanceof CSSStyleRule) {
      entries.push({ kind: 'style', rule, baseUrl })
    } else {
      // @keyframes、@property 等:cssText 原样保留
      entries.push({ kind: 'raw', text: rule.cssText, baseUrl })
    }
  }
}

async function buildSnapshotCss(codes, cssW, cssH) {
  const entries = []
  for (const sheet of document.styleSheets) {
    let rules
    try {
      rules = sheet.cssRules
    } catch (e) {
      continue // 跨域样式表读不到规则,跳过
    }
    collectRuleEntries(entries, rules, sheet.href || document.baseURI)
  }

  // 决定哪些 @font-face 需要内联(其余整条丢弃,省掉几百 KB 的 CJK 字体)
  for (const e of entries) {
    if (e.kind === 'font') {
      const rangeText = e.rule.style ? e.rule.style.getPropertyValue('unicode-range') : ''
      e.needed = !rangeText || !rangeText.trim() || faceCoversChars(rangeText, codes)
    }
  }

  // 预抓取所有 url() 引用(字体、背景图等),统一转 data URL
  const urlPromises = new Map()
  const gatherUrls = (text, baseUrl) => {
    text.replace(URL_RE, (m, q, u) => {
      if (u && !u.startsWith('data:')) {
        try {
          const abs = new URL(u, baseUrl).href
          if (!urlPromises.has(abs)) urlPromises.set(abs, fetchAsDataUrl(abs))
        } catch (e) { /* 非法 URL,保留原样 */ }
      }
      return m
    })
  }
  const scanUrls = (list) => {
    for (const e of list) {
      if (e.kind === 'block') { scanUrls(e.children); continue }
      if (e.kind === 'font' && !e.needed) continue
      const text = e.kind === 'raw' ? e.text : (e.rule.style ? e.rule.style.cssText : '')
      if (text) gatherUrls(text, e.baseUrl)
    }
  }
  scanUrls(entries)

  const resolved = new Map()
  await Promise.all(
    Array.from(urlPromises.entries()).map(async ([abs, p]) => {
      try { resolved.set(abs, await p) } catch (e) { /* 失败则保留原引用 */ }
    })
  )

  // 外部引用内联;解析失败的一律换成空 data URL ——
  // SVG 图片里只要残留一个外部 URL,整张 canvas 就会被污染,
  // WebGL texImage2D 会抛 SecurityError 导致整个 CRT 管线降级
  const replaceUrls = (text, baseUrl) =>
    text.replace(URL_RE, (m, q, u) => {
      if (!u || u.startsWith('data:')) return m
      try {
        const du = resolved.get(new URL(u, baseUrl).href)
        return du ? 'url("' + du + '")' : 'url("data:,")'
      } catch (e) {
        return 'url("data:,")'
      }
    })

  const emit = (e) => {
    if (e.kind === 'font') {
      if (!e.needed || !e.rule.style) return ''
      return '@font-face{' + replaceUrls(viewportUnitsToPx(e.rule.style.cssText, cssW, cssH), e.baseUrl) + '}'
    }
    if (e.kind === 'style') {
      if (!e.rule.style) return ''
      const sel = rewriteSelector(e.rule.selectorText)
      if (!sel) return ''
      return sel + '{' + replaceUrls(viewportUnitsToPx(e.rule.style.cssText, cssW, cssH), e.baseUrl) + '}'
    }
    return replaceUrls(viewportUnitsToPx(e.text, cssW, cssH), e.baseUrl)
  }

  const emitAll = (list) => {
    const parts = []
    for (const e of list) {
      if (e.kind === 'block') {
        const inner = emitAll(e.children)
        if (inner) parts.push(e.prefix + '{' + inner + '}')
      } else {
        const t = emit(e)
        if (t) parts.push(t)
      }
    }
    return parts.join('\n')
  }
  return emitAll(entries)
}

// ── 克隆准备(同步,临时改动真实 DOM,用完立即还原) ─────────────────────────

function buildPreparedSnapshot(sourceEl) {
  const marks = []      // 被打过标记的真实 DOM 元素
  let nextId = 1
  // 每个元素一个标记、可挂多个动作。
  // 之前的实现里一个元素只能带一个 id:元素先被标记了动作 A(如滚动平移),
  // 后续扫描再标记动作 B(如 hover)会把 A 的 id 覆盖掉,导致 A 静默丢失
  // —— 表格悬停时内容不再滚动、表头偶尔被内容穿越,都是这个覆盖 bug。
  const slots = new Map()   // realEl -> { id, fns: [] }
  const slotOf = (el) => {
    let slot = slots.get(el)
    if (!slot) {
      const id = 's' + nextId++
      el.setAttribute(MARK_ATTR, id)
      marks.push(el)
      slot = { id, fns: [] }
      slots.set(el, slot)
    }
    return slot
  }
  const imgJobs = []    // { el(克隆后回填), src }

  const all = [sourceEl].concat(Array.from(sourceEl.querySelectorAll('*')))
  const elements = all.filter((o) => o instanceof Element)

  // 判断 sticky 元素当前是否处于"钉住"状态:
  // 临时改成 static 比较两次渲染矩形,不同即被钉住
  const stuckRect = (el) => {
    const r0 = el.getBoundingClientRect()
    const prev = el.style.position
    el.style.position = 'static'
    const r1 = el.getBoundingClientRect()
    el.style.position = prev
    if (Math.abs(r0.top - r1.top) > 1 || Math.abs(r0.left - r1.left) > 1) return r0
    return null
  }

  // ── 第一遍:分类 ──────────────────────────────────────────────────────────
  const hovered = []
  const focused = []
  const scrollables = []   // { el, st, sl, isStatic }
  const scrollableSet = new Set()
  for (const o of elements) {
    try {
      // :hover 供直通模式;__crt_hover 类供指针接管模式(canvas 拦截
      // 事件后真实 DOM 永远不处于 :hover,悬停态由坐标反算后显式标记)
      if (o.matches(':hover') || (o.classList && o.classList.contains('__crt_hover'))) hovered.push(o)
      if (o.matches(':focus') || (o.classList && o.classList.contains('__crt_focus'))) focused.push(o)
    } catch (e) { /* 非常规元素,忽略 */ }

    if (o.tagName === 'IMG') {
      const src = o.getAttribute('src') || ''
      if (src && !src.startsWith('data:')) imgJobs.push({ el: null, src, slot: slotOf(o) })
    }

    if (o.scrollHeight > o.clientHeight + 1 || o.scrollWidth > o.clientWidth + 1) {
      let isStatic = true
      try { isStatic = getComputedStyle(o).position === 'static' } catch (e) { /* 按 static 处理 */ }
      scrollables.push({ el: o, st: o.scrollTop, sl: o.scrollLeft, isStatic })
      scrollableSet.add(o)
    }
  }

  // ── 第二遍:构建修改动作 ─────────────────────────────────────────────────
  for (const o of hovered) slotOf(o).fns.push((c) => c.classList.add('__crt_hover'))
  for (const o of focused) slotOf(o).fns.push((c) => c.classList.add('__crt_focus'))

  for (const { el, isStatic } of scrollables) {
    slotOf(el).fns.push((c) => {
      // 可滚动容器一律去掉滚动条(快照里不该出现系统滚动条),
      // 同时作为粘性元素绝对定位的锚点
      c.style.overflow = 'hidden'
      if (isStatic) c.style.position = 'relative'
    })
  }

  for (const { el, st, sl } of scrollables) {
    if (st <= 0 && sl <= 0) continue
    // 滚动补偿:直接子元素整体平移 -scrollTop/-scrollLeft
    for (const kid of el.children) {
      const kidSlot = slotOf(kid)
      const t = 'translate(' + -sl + 'px,' + -st + 'px)'
      kidSlot.fns.push((c) => {
        c.style.transform = c.style.transform ? t + ' ' + c.style.transform : t
      })
    }
  }

  // 粘性元素:找最近的滚动容器(避免外层容器抢占);
  // 钉住状态下 → 隐藏占位符保布局 + 移到滚动容器直属子级绝对定位。
  // 同一父元素的粘性兄弟(如同一行的多个 th)整组装进一个定位包装器:
  // 单独移出会破坏 th:first-child / th:last-child 这类结构选择器,
  // 导致首列边框等样式丢失;包装器内保持兄弟顺序即可恢复匹配
  const stickyGroups = new Map()   // parentEl -> [{el, rect}]
  for (const s of elements) {
    let pos
    try { pos = getComputedStyle(s).position } catch (e) { continue }
    if (pos !== 'sticky') continue

    let container = null
    for (let p = s.parentElement; p && p !== sourceEl.parentElement; p = p.parentElement) {
      if (scrollableSet.has(p)) { container = p; break }
      if (p === sourceEl) break
    }
    if (!container) continue

    const rect = stuckRect(s)
    if (!rect) continue

    let g = stickyGroups.get(s.parentElement)
    if (!g) { g = { parent: s.parentElement, container, items: [] }; stickyGroups.set(s.parentElement, g) }
    else if (g.container !== container) continue
    g.items.push({ el: s, rect })
  }

  for (const g of stickyGroups.values()) {
    const oRect = g.container.getBoundingClientRect()
    const gRect = g.items[0].rect
    let z = 'auto'
    try { z = getComputedStyle(g.items[0].el).zIndex } catch (e) { /* 保持 auto */ }
    const relTop = gRect.top - oRect.top
    const relLeft = gRect.left - oRect.left
    const containerSlot = slotOf(g.container)
    const containerId = containerSlot.id

    // 包装器在每个快照的 apply 阶段创建,组内元素共享(闭包状态)
    let wrapperEl = null

    for (const { el: s, rect } of g.items) {
      const width = rect.width
      const height = rect.height
      const offTop = rect.top - gRect.top
      const offLeft = rect.left - gRect.left

      slotOf(s).fns.push((c) => {
        const holder = c.cloneNode(true)
        holder.style.visibility = 'hidden'
        holder.style.position = 'static'
        if (c.parentNode) c.parentNode.insertBefore(holder, c)
        // 必须把钉住的元素移出被平移的子树:transform 元素会成为
        // 绝对定位后代的包含块,留在原地会被二次平移飞出可视区。
        // 包装器挂在滚动容器(未被平移、position:relative)直属子级,
        // 元素在包装器内保持原兄弟顺序 → 结构选择器(:first-child 等)照常生效
        if (!wrapperEl) {
          wrapperEl = document.createElement('div')
          wrapperEl.style.position = 'absolute'
          wrapperEl.style.top = relTop + 'px'
          wrapperEl.style.left = relLeft + 'px'
          wrapperEl.style.zIndex = (z !== 'auto' ? z : '10')
          const containerClone = findInClone(containerId)
          if (containerClone) containerClone.appendChild(wrapperEl)
        }
        wrapperEl.appendChild(c)
        c.style.position = 'absolute'
        c.style.top = offTop + 'px'
        c.style.left = offLeft + 'px'
        c.style.width = width + 'px'
        c.style.height = height + 'px'
        c.style.margin = '0'
      })
    }
  }

  const clone = sourceEl.cloneNode(true)

  // 关键:真实 DOM 靠 crt-hidden(opacity:0)隐藏,克隆体若带着这个类,
  // 收集的 CSS 会让整个快照变透明 → 纹理全黑。克隆后立即摘掉
  clone.classList && clone.classList.remove('crt-hidden')

  // 立即清理真实 DOM 上的标记(克隆已经带上了这些属性)
  for (const el of marks) el.removeAttribute(MARK_ATTR)

  const findInClone = (id) => {
    if (clone.getAttribute && clone.getAttribute(MARK_ATTR) === id) return clone
    return clone.querySelector('[' + MARK_ATTR + '="' + id + '"]')
  }

  for (const [, slot] of slots) {
    const c = findInClone(slot.id)
    if (!c) continue
    for (const fn of slot.fns) fn(c)
  }
  // 图片 data URL 在异步阶段解析,这里先回填克隆元素
  for (const job of imgJobs) job.el = findInClone(job.slot.id)

  // 清掉克隆树上的标记属性
  const marked = clone.querySelectorAll('[' + MARK_ATTR + ']')
  for (const el of marked) el.removeAttribute(MARK_ATTR)
  if (clone.hasAttribute && clone.hasAttribute(MARK_ATTR)) clone.removeAttribute(MARK_ATTR)

  // 收集页面用到的字符码点(决定内联哪些字体)
  const codes = new Set()
  const text = clone.textContent || ''
  for (const ch of text) codes.add(ch.codePointAt(0))

  return { sourceEl, clone, codes, imgJobs }
}

// ── SVG 组装与解码 ──────────────────────────────────────────────────────────

function escapeXmlText(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function buildSvgString(cloneHtml, cssText, cssW, cssH, dpr) {
  const W = Math.max(1, Math.round(cssW * dpr))
  const H = Math.max(1, Math.round(cssH * dpr))
  const htmlStyle = (document.documentElement && document.documentElement.getAttribute('style')) || ''
  const bodyEl = document.body
  const bodyClass = bodyEl ? bodyEl.getAttribute('class') || '' : ''
  const bodyStyle = bodyEl ? bodyEl.getAttribute('style') || '' : ''

  return (
    '<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '">' +
    '<foreignObject x="0" y="0" width="' + W + '" height="' + H + '">' +
    '<div xmlns="' + XHTML_NS + '" style="width:' + W + 'px;height:' + H + 'px;overflow:hidden;">' +
    '<div class="__crt_root" style="width:' + cssW + 'px;height:' + cssH + 'px;transform:scale(' + dpr + ');transform-origin:0 0;' + htmlStyle + '">' +
    '<div class="__crt_body ' + bodyClass + '" style="width:' + cssW + 'px;height:' + cssH + 'px;' + bodyStyle + '">' +
    '<style>' + escapeXmlText(cssText) + '</style>' +
    cloneHtml +
    '</div></div></div></foreignObject></svg>'
  )
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = async () => {
      try { if (img.decode) await img.decode() } catch (e) { /* decode 失败也继续,onload 已触发 */ }
      resolve(img)
    }
    img.onerror = () => reject(new Error('snapshot SVG failed to decode'))
    img.src = url
  })
}

// ── 对外 API ────────────────────────────────────────────────────────────────

/**
 * 第一步(同步):克隆 DOM 并修正滚动/粘性/交互态。
 * 调用方应在这步前后暂停/恢复 MutationObserver,
 * 因为内部会短暂修改真实 DOM(打标记、探测 sticky)。
 */
export function prepareSnapshot(sourceEl) {
  return buildPreparedSnapshot(sourceEl)
}

/**
 * 第二步(异步):解析资源 → 序列化 SVG → 解码 → 画到目标 canvas。
 * 返回 { width, height, cssWidth, cssHeight, dpr };失败抛异常。
 */
export async function renderSnapshot(prep, targetCanvas) {
  const sourceEl = prep.sourceEl
  const cssW = sourceEl.clientWidth
  const cssH = sourceEl.clientHeight
  if (!cssW || !cssH) throw new Error('source element has no size')

  const dpr = Math.min(window.devicePixelRatio || 1, DPR_CAP)
  const W = Math.max(1, Math.round(cssW * dpr))
  const H = Math.max(1, Math.round(cssH * dpr))

  // 图片内联;失败则换空 data URL,避免外部引用污染 canvas
  for (const job of prep.imgJobs) {
    if (!job.el) continue
    try {
      const abs = new URL(job.src, document.baseURI).href
      const du = await fetchAsDataUrl(abs)
      job.el.setAttribute('src', du)
    } catch (e) {
      job.el.setAttribute('src', 'data:,')
    }
  }

  const cssText = await buildSnapshotCss(prep.codes, cssW, cssH)
  const cloneHtml = new XMLSerializer().serializeToString(prep.clone)
  const svg = buildSvgString(cloneHtml, cssText, cssW, cssH, dpr)

  // 用 data: URL 而非 blob: URL 加载 SVG:
  // Chrome 对含 foreignObject 的 blob-SVG 图片绘制后会将 canvas 标记为污染,
  // 导致 WebGL texImage2D 抛 SecurityError;data: URL 则始终同源安全
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
  const img = await loadImage(url)

  if (targetCanvas.width !== W) targetCanvas.width = W
  if (targetCanvas.height !== H) targetCanvas.height = H
  const ctx = targetCanvas.getContext('2d')
  ctx.clearRect(0, 0, W, H)
  ctx.drawImage(img, 0, 0, W, H)

  return { width: W, height: H, cssWidth: cssW, cssHeight: cssH, dpr }
}
