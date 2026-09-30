/**
 * CRT 屏幕着色器(GLSL ES 3.0 / WebGL2)
 *
 * 几何部分移植自 Mega Bezel(HyperspaceMadness,GPLv3):
 *   - crtPiCurve   ← HSM_GetCrtPiCurvedCoord(cgwg CRT-Pi 的桶形畸变核心)
 *   - curvedUV     ← HSM_Get2DCurvedCoord(边缘补偿:弯曲后画面仍撑满屏幕边缘)
 *   - cornerMask   ← HSM_GetCornerMask(圆角玻璃遮罩)
 * 扫描线/荫罩/暗角参考了 apple2js 的 screenEmu 分析:
 * 所有屏幕效果都作用在"弯曲后的坐标"上,网格跟着玻璃一起弯。
 */

export const VERT_SRC = `#version 300 es
layout(location = 0) in vec2 aPos;
out vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}
`

export const FRAG_SRC = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 outColor;

uniform sampler2D uScreen;   // DOM 内容快照(mipmap,供 bloom 采样)
uniform sampler2D uPrev;     // 上一帧输出(荧光粉余晖)
uniform vec2  uResolution;   // 画布物理像素
uniform vec2  uCssSize;      // 画布 CSS 像素(扫描线/荫罩按 CSS 像素密度计算)
uniform float uTime;
uniform vec2  uBarrel;       // 桶形畸变强度 {x, y},0 = 关闭,典型 0.02 ~ 0.2
uniform float uZoom;         // 内容预放大
uniform float uScanOpacity;  // 扫描线暗度
uniform float uScanCount;    // 屏幕高度方向可见扫描线数
uniform float uMaskOpacity;  // 荫罩强度
uniform float uVignette;     // 暗角强度
uniform float uGlow;         // 荧光辉光(bloom)强度 0~1
uniform float uFlicker;      // 闪烁强度
uniform float uPersistence;  // 余晖保持系数 0~1
uniform float uCorner;       // 圆角半径(以屏幕半高为 1.0 的比例)
uniform float uCornerSharp;  // 圆角边缘锐度

const float PI = 3.14159265358979;

// ---- Mega Bezel: HSM_GetCrtPiCurvedCoord -------------------------------
// p' = p * (1 + k*r^2) 再乘 barrelScale 部分抵消收缩
vec2 crtPiCurve(vec2 uv, vec2 k) {
  vec2 kk = k * 5.0;
  vec2 barrelScale = 1.0 - 0.23 * kk;
  uv -= vec2(0.5);
  float rsq = uv.x * uv.x + uv.y * uv.y;
  uv += uv * (kk * rsq);
  uv *= barrelScale;
  return uv + vec2(0.5);
}

// ---- Mega Bezel: HSM_Get2DCurvedCoord ----------------------------------
// 畸变会让画面缩小、边缘够不到屏幕边;分别对右边缘中点和下边缘中点
// 求一次弯曲坐标,把整体坐标按比例放大回来,保证四边仍贴住屏幕。
vec2 curvedUV(vec2 uv, vec2 k) {
  vec2 c = crtPiCurve(uv, k) - vec2(0.5);
  vec2 right  = crtPiCurve(vec2(1.0, 0.5), k) - vec2(0.5);
  vec2 bottom = crtPiCurve(vec2(0.5, 1.0), k) - vec2(0.5);
  c.x *= 0.5 / max(abs(right.x), 1e-5);
  c.y *= 0.5 / max(abs(bottom.y), 1e-5);
  return c + vec2(0.5);
}

// ---- Mega Bezel: HSM_GetCornerMask(cgwg 圆角距离场) --------------------
float cornerMask(vec2 uv, float aspect) {
  vec2 p = min(uv, vec2(1.0) - uv) * vec2(aspect, 1.0);
  vec2 cd = vec2(max(uCorner, 0.0005));
  p = cd - min(p, cd);
  float d = length(p);
  return clamp((cd.x - d) * uCornerSharp, 0.0, 1.0);
}

void main() {
  float aspect = uResolution.x / max(uResolution.y, 1.0);

  // 预放大 → 桶形畸变(反向映射:每个输出像素问"去源图哪里采样")
  vec2 uvz = (vUv - vec2(0.5)) / max(uZoom, 0.001) + vec2(0.5);
  vec2 uv = curvedUV(uvz, uBarrel);

  bool inside = uv.x > 0.0 && uv.x < 1.0 && uv.y > 0.0 && uv.y < 1.0;

  vec3 col = vec3(0.0);
  if (inside) {
    col = texture(uScreen, uv).rgb;

    // 荧光辉光:对 mip 高层采样得到低频亮度,叠加回来
    if (uGlow > 0.001) {
      float lod = 1.5 + uGlow * 2.5;
      vec3 bloom = textureLod(uScreen, clamp(uv, vec2(0.001), vec2(0.999)), lod).rgb;
      col += col * uGlow * 0.6 + bloom * uGlow * 0.8;
    }
  }

  if (inside) {
    // 扫描线:弯曲空间里的正弦调制,网格随玻璃弯曲
    float sl = sin(PI * uScanCount * uv.y);
    col *= mix(1.0, sl * sl, uScanOpacity);

    // 荫罩:竖向 RGB 三色栅条(弯曲空间,3 CSS 像素一组)
    if (uMaskOpacity > 0.001) {
      float f = fract(uv.x * uCssSize.x / 3.0);
      vec3 grille = f < 0.3333 ? vec3(1.0, 0.55, 0.55)
                  : f < 0.6666 ? vec3(0.55, 1.0, 0.55)
                               : vec3(0.55, 0.55, 1.0);
      col *= mix(vec3(1.0), grille * 1.45, uMaskOpacity);
    }
  }

  // 暗角:中心亮四周暗的指数衰减(作用在弯曲坐标上)
  // 系数上限压低,避免边角全黑盖住桶形畸变
  vec2 vc = (uv - vec2(0.5)) * 2.0 * (0.25 + uVignette * 0.6);
  col *= exp(-dot(vc, vc));

  // 圆角玻璃遮罩(弯曲后的屏幕四角被削圆)
  col *= cornerMask(uv, aspect);

  // 闪烁:多个不可通约频率的正弦叠加,避免周期感
  if (uFlicker > 0.0001) {
    float fl = sin(uTime * 120.0) * sin(uTime * 77.7 + 1.3) * sin(uTime * 33.1 + 2.1);
    col *= 1.0 - uFlicker * (0.5 + 0.5 * fl);
  }

  // 荧光粉余晖:与衰减后的上一帧取 max(亮点拖尾)
  if (uPersistence > 0.001) {
    vec3 prev = texture(uPrev, vUv).rgb;
    col = max(col, prev * uPersistence);
  }

  outColor = vec4(col, 1.0);
}
`

// 余晖开启时,合成 pass 画到 FBO,再用这个拷贝 pass 上屏
export const COPY_SRC = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 outColor;
uniform sampler2D uTex;
void main() {
  outColor = texture(uTex, vUv);
}
`
