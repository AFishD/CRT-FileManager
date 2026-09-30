/**
 * WebGL2 CRT 渲染器
 *
 * 职责:把栅格化好的 DOM 快照作为纹理,按 Mega Bezel 移植的着色器
 * 渲染到画布上;荧光粉余晖开启时走 FBO 双缓冲(合成 → 拷贝上屏 → 交换)。
 *
 * 纹理坐标约定:内容纹理上传时设置 UNPACK_FLIP_Y_WEBGL,
 * 顶点着色器输出的 vUv(0,0 在左下)与 canvas 像素行序对齐。
 */

import { VERT_SRC, FRAG_SRC, COPY_SRC } from './shaders.js'

const UNIFORM_NAMES = [
  'uScreen', 'uPrev', 'uResolution', 'uCssSize', 'uTime',
  'uBarrel', 'uZoom', 'uScanOpacity', 'uScanCount', 'uMaskOpacity',
  'uVignette', 'uGlow', 'uFlicker', 'uPersistence', 'uCorner', 'uCornerSharp'
]

export class CRTRenderer {
  constructor(canvas) {
    const gl = canvas.getContext('webgl2', {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      premultipliedAlpha: false,
      preserveDrawingBuffer: false
    })
    if (!gl) throw new Error('WebGL2 not available')
    this.gl = gl
    this.canvas = canvas

    this.prog = this._buildProgram(VERT_SRC, FRAG_SRC)
    this.copyProg = this._buildProgram(VERT_SRC, COPY_SRC)

    this.u = {}
    for (const name of UNIFORM_NAMES) {
      this.u[name] = gl.getUniformLocation(this.prog, name)
    }
    this.cu = { uTex: gl.getUniformLocation(this.copyProg, 'uTex') }

    // 全屏三角形 + VAO(两个程序共用)
    const vao = gl.createVertexArray()
    gl.bindVertexArray(vao)
    const buf = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buf)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
    gl.enableVertexAttribArray(0)
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0)
    gl.bindVertexArray(null)
    this.vao = vao
    this._buf = buf

    // 内容纹理(带 mipmap,bloom 采样 mip 高层)
    this.contentTex = gl.createTexture()
    gl.bindTexture(gl.TEXTURE_2D, this.contentTex)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255]))
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)

    // 黑色纹理(余晖关闭时占位 uPrev)
    this.blackTex = gl.createTexture()
    gl.bindTexture(gl.TEXTURE_2D, this.blackTex)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255]))
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)

    this.fbA = null
    this.fbB = null
    this.texA = null
    this.texB = null
    this.fbSize = [0, 0]

    this.params = {
      barrelX: 0.08, barrelY: 0.08, zoom: 1.02,
      scanOpacity: 0.3, scanCount: 540,
      maskOpacity: 0.06, vignette: 0.5, glow: 0.17,
      flicker: 0.03, persistence: 0.25,
      corner: 0.03, cornerSharp: 800
    }
    this.cssSize = [1, 1]
    this.hasContent = false
  }

  _buildProgram(vsSrc, fsSrc) {
    const gl = this.gl
    const compile = (type, src) => {
      const sh = gl.createShader(type)
      gl.shaderSource(sh, src)
      gl.compileShader(sh)
      if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
        const log = gl.getShaderInfoLog(sh)
        gl.deleteShader(sh)
        throw new Error('shader compile failed: ' + log)
      }
      return sh
    }
    const vs = compile(gl.VERTEX_SHADER, vsSrc)
    const fs = compile(gl.FRAGMENT_SHADER, fsSrc)
    const prog = gl.createProgram()
    gl.attachShader(prog, vs)
    gl.attachShader(prog, fs)
    gl.linkProgram(prog)
    gl.deleteShader(vs)
    gl.deleteShader(fs)
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      const log = gl.getProgramInfoLog(prog)
      gl.deleteProgram(prog)
      throw new Error('program link failed: ' + log)
    }
    return prog
  }

  setParameters(p) {
    Object.assign(this.params, p)
  }

  /** 上传 DOM 快照(来自 rasterizer 的 2D canvas) */
  uploadContent(canvas2d) {
    const gl = this.gl
    gl.bindTexture(gl.TEXTURE_2D, this.contentTex)
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, canvas2d)
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false)
    gl.generateMipmap(gl.TEXTURE_2D)
    this.hasContent = true
  }

  resize(cssW, cssH, dpr) {
    const w = Math.max(1, Math.round(cssW * dpr))
    const h = Math.max(1, Math.round(cssH * dpr))
    if (this.canvas.width !== w) this.canvas.width = w
    if (this.canvas.height !== h) this.canvas.height = h
    this.cssSize = [cssW, cssH]

    if (this.fbSize[0] !== w || this.fbSize[1] !== h) {
      this._destroyFramebuffers()
      this.texA = this._makeTargetTexture(w, h)
      this.texB = this._makeTargetTexture(w, h)
      this.fbA = this._makeFramebuffer(this.texA)
      this.fbB = this._makeFramebuffer(this.texB)
      this.fbSize = [w, h]
    }
  }

  _makeTargetTexture(w, h) {
    const gl = this.gl
    const tex = gl.createTexture()
    gl.bindTexture(gl.TEXTURE_2D, tex)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
    return tex
  }

  _makeFramebuffer(tex) {
    const gl = this.gl
    const fb = gl.createFramebuffer()
    gl.bindFramebuffer(gl.FRAMEBUFFER, fb)
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0)
    gl.bindFramebuffer(gl.FRAMEBUFFER, null)
    return fb
  }

  _destroyFramebuffers() {
    const gl = this.gl
    for (const fb of [this.fbA, this.fbB]) if (fb) gl.deleteFramebuffer(fb)
    for (const tex of [this.texA, this.texB]) if (tex) gl.deleteTexture(tex)
    this.fbA = this.fbB = this.texA = this.texB = null
    this.fbSize = [0, 0]
  }

  /** 渲染一帧。tSec:秒级时间戳 */
  render(tSec) {
    const gl = this.gl
    const p = this.params
    const w = this.canvas.width
    const h = this.canvas.height

    gl.bindVertexArray(this.vao)
    gl.useProgram(this.prog)

    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, this.contentTex)
    gl.uniform1i(this.u.uScreen, 0)

    const usePersistence = p.persistence > 0.001 && this.fbA
    gl.activeTexture(gl.TEXTURE1)
    gl.bindTexture(gl.TEXTURE_2D, usePersistence ? this.texA : this.blackTex)
    gl.uniform1i(this.u.uPrev, 1)

    gl.uniform2f(this.u.uResolution, w, h)
    gl.uniform2f(this.u.uCssSize, this.cssSize[0], this.cssSize[1])
    gl.uniform1f(this.u.uTime, tSec)
    gl.uniform2f(this.u.uBarrel, p.barrelX, p.barrelY)
    gl.uniform1f(this.u.uZoom, p.zoom)
    gl.uniform1f(this.u.uScanOpacity, p.scanOpacity)
    gl.uniform1f(this.u.uScanCount, p.scanCount)
    gl.uniform1f(this.u.uMaskOpacity, p.maskOpacity)
    gl.uniform1f(this.u.uVignette, p.vignette)
    gl.uniform1f(this.u.uGlow, p.glow)
    gl.uniform1f(this.u.uFlicker, p.flicker)
    gl.uniform1f(this.u.uPersistence, p.persistence)
    gl.uniform1f(this.u.uCorner, p.corner)
    gl.uniform1f(this.u.uCornerSharp, p.cornerSharp)

    if (usePersistence) {
      // 合成到 FBO B(uPrev 读 FBO A),再拷贝上屏,最后交换
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbB)
      gl.viewport(0, 0, w, h)
      gl.drawArrays(gl.TRIANGLES, 0, 3)

      gl.bindFramebuffer(gl.FRAMEBUFFER, null)
      gl.viewport(0, 0, w, h)
      gl.useProgram(this.copyProg)
      gl.activeTexture(gl.TEXTURE0)
      gl.bindTexture(gl.TEXTURE_2D, this.texB)
      gl.uniform1i(this.cu.uTex, 0)
      gl.drawArrays(gl.TRIANGLES, 0, 3)

      const t_fb = this.fbA; this.fbA = this.fbB; this.fbB = t_fb
      const t_tex = this.texA; this.texA = this.texB; this.texB = t_tex
    } else {
      gl.bindFramebuffer(gl.FRAMEBUFFER, null)
      gl.viewport(0, 0, w, h)
      gl.drawArrays(gl.TRIANGLES, 0, 3)
    }

    gl.bindVertexArray(null)
  }

  dispose() {
    const gl = this.gl
    this._destroyFramebuffers()
    gl.deleteTexture(this.contentTex)
    gl.deleteTexture(this.blackTex)
    if (this._buf) gl.deleteBuffer(this._buf)
    if (this.vao) gl.deleteVertexArray(this.vao)
    gl.deleteProgram(this.prog)
    gl.deleteProgram(this.copyProg)
  }
}
