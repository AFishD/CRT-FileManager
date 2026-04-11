<template>
  <div class="crt-monitor">
    <!-- CRT显示器外壳 -->
    <div class="crt-bezel">
      <!-- CRT屏幕玻璃 -->
      <div class="crt-screen" :class="{ 'crt-enabled': effectsEnabled }">
        <!-- 内容层 -->
        <div class="crt-content" :style="contentStyle">
          <slot></slot>
        </div>

        <!-- 扫描线层 (CSS repeating-linear-gradient - 参考apple2.css .scanlines::after) -->
        <div v-if="effectsEnabled" class="crt-scanlines"></div>

        <!-- RGB荫罩/荧光粉点阵层 (Shadow Mask - 参考screenEmu.js shadowMask纹理) -->
        <div v-if="effectsEnabled" class="crt-shadow-mask"></div>

        <!-- 暗角/中心高光层 (Vignetting - 参考 exp(-dot(lighting, lighting)) 指数衰减) -->
        <div v-if="effectsEnabled" class="crt-vignette"></div>

        <!-- 屏幕玻璃反光层 -->
        <div v-if="effectsEnabled" class="crt-reflection"></div>

        <!-- 闪烁层 (Flicker) -->
        <div v-if="effectsEnabled" class="crt-flicker"></div>
      </div>
    </div>

    <!-- 电源指示灯 -->
    <div class="crt-power-led" :class="{ 'on': effectsEnabled }"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  config: {
    type: Object,
    required: true
  }
});

const effectsEnabled = computed(() => {
  return props.config?.crt_effects?.enabled ?? true;
});

const crtConfig = computed(() => {
  return props.config?.crt_effects ?? {};
});

const contentStyle = computed(() => {
  if (!effectsEnabled.value) {
    return {};
  }

  const glow = crtConfig.value.glow || { strength: '0.5px', color: 'rgba(255, 255, 255, 0.4)' };
  const distortion = crtConfig.value.distortion || { zoom: 1.02 };

  return {
    textShadow: `0 0 ${glow.strength} ${glow.color}`,
    // 轻微缩放模拟桶形畸变的中心放大效果（参考分析文档中的 barrelSize）
    transform: `scale(${distortion.zoom})`,
  };
});
</script>

<style scoped>
/*
 * ============================================================================
 * CRT 显示器完整效果实现
 * 
 * 基于 apple2js 项目 CRT_Barrel_Distortion_Analysis.md 分析文档
 * 实现了以下CRT物理特性：
 *   1. 桶形畸变 (Barrel Distortion) - CSS border-radius + mask 模拟
 *   2. 扫描线 (Scanlines) - repeating-linear-gradient
 *   3. 荫罩/荧光粉 (Shadow Mask) - 细密RGB条纹渐变
 *   4. 暗角效果 (Vignetting) - radial-gradient 指数衰减
 *   5. 屏幕闪烁 (Flicker) - CSS opacity animation
 *   6. 荧光粉余晖 (Persistence) - CSS text-shadow glow
 *   7. 屏幕反光 (Glass Reflection) - 线性渐变高光
 * ============================================================================
 */

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

/* === 显示器边框/挡板 === */
.crt-bezel {
  width: 100%;
  height: 100%;
  position: relative;
  /* 边框内间距模拟CRT显示器的黑色边框 */
  padding: 12px;
  box-sizing: border-box;
  background: #0a0a0a;
  /* 挡板的微妙立体效果 */
  box-shadow:
    inset 0 0 60px rgba(0, 0, 0, 0.8),
    inset 0 0 3px rgba(255, 255, 255, 0.03);
}

/* === CRT屏幕玻璃 === */
.crt-screen {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: #000000;
}

.crt-screen.crt-enabled {
  /*
   * 桶形畸变模拟 (Barrel Distortion Simulation)
   * -----------------------------------------------
   * 参考文档中的 WebGL 实现: qb = barrel * qc * dot(qc, qc)
   * 
   * 由于我们处理的是 DOM 内容而非 Canvas，无法使用 WebGL Fragment Shader。
   * 这里使用 CSS border-radius 模拟 CRT 曲面玻璃的圆角效果，
   * 配合 mask/vignette 模拟边缘的视觉压缩，达到近似桶形畸变的外观。
   */
  border-radius: 18px;

  /*
   * CSS Mask 实现边缘渐隐 (Vignetting through Mask)
   * -----------------------------------------------
   * 参考文档: vec2 lighting = qc * centerLighting;
   *          c *= exp(-dot(lighting, lighting));
   * 
   * 使用 radial-gradient 作为 mask，中心完全可见，
   * 边缘逐渐透明，模拟 CRT 的电子束边缘衰减。
   */
  -webkit-mask: radial-gradient(
    ellipse 96% 96% at 50% 50%,
    black 60%,
    rgba(0, 0, 0, 0.85) 75%,
    rgba(0, 0, 0, 0.4) 90%,
    transparent 100%
  );
  mask: radial-gradient(
    ellipse 96% 96% at 50% 50%,
    black 60%,
    rgba(0, 0, 0, 0.85) 75%,
    rgba(0, 0, 0, 0.4) 90%,
    transparent 100%
  );
}

/* === 内容层 === */
.crt-content {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;
  transform-origin: center center;
}

/* === 扫描线效果 (Scanlines) === */
/*
 * 参考文档 3.1 节:
 * CSS方式 - repeating-linear-gradient
 * 
 * 参考 apple2.css:
 *   .scanlines::after {
 *     background-image: repeating-linear-gradient(
 *       to bottom, transparent 0, transparent 1px,
 *       rgba(0, 0, 0, 0.5) 1px, rgba(0, 0, 0, 0.5) 2px
 *     );
 *   }
 * 
 * 同时参考 Shader 方式:
 *   float scanline = sin(PI * textureSize.y * q.y);
 *   c *= mix(1.0, scanline * scanline, scanlineLevel);
 */
.crt-scanlines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
  pointer-events: none;

  /* 扫描线 - 每2px一组，1px透明+1px半透明黑色 */
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent 1px,
    rgba(0, 0, 0, 0.3) 1px,
    rgba(0, 0, 0, 0.3) 2px
  );
  background-size: 100% 2px;

  /* 扫描线轻微移动动画 - 模拟CRT刷新 */
  animation: scanline-scroll 10s linear infinite;
}

@keyframes scanline-scroll {
  0% {
    transform: translateY(0);
  }
  100% {
    transform: translateY(4px);
  }
}

/* === 荫罩/荧光粉点阵 (Shadow Mask / Phosphor Grid) === */
/*
 * 参考文档 3.2 节:
 * 彩色CRT的红绿蓝三原色荧光粉点阵
 * 
 * Shader实现:
 *   vec3 mask = texture2D(shadowMask, (v_texCoord2 + qb) * shadowMaskSize).rgb;
 *   c *= mix(vec3(1.0, 1.0, 1.0), mask, shadowMaskLevel);
 * 
 * CSS使用 repeating-linear-gradient 模拟 SHADOWMASK_TRIAD 纹理
 * 每3px一组RGB亚像素（红、绿、蓝条纹）
 */
.crt-shadow-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 3;
  pointer-events: none;
  opacity: 0.06;

  /* RGB三基色荫罩条纹 */
  background-image: repeating-linear-gradient(
    to right,
    rgba(255, 0, 0, 1) 0px,
    rgba(255, 0, 0, 1) 1px,
    rgba(0, 255, 0, 1) 1px,
    rgba(0, 255, 0, 1) 2px,
    rgba(0, 0, 255, 1) 2px,
    rgba(0, 0, 255, 1) 3px
  );
  background-size: 3px 100%;
}

/* === 暗角效果 (Vignetting Overlay) === */
/*
 * 参考文档 3.3 节:
 * 屏幕中心高光 / 边缘暗角
 *
 * Shader实现:
 *   vec2 lighting = qc * centerLighting;
 *   c *= exp(-dot(lighting, lighting));
 * 
 * 使用 radial-gradient 模拟以自然常数e为底的指数衰减
 * 距离中心越远，亮度衰减越厉害
 */
.crt-vignette {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 4;
  pointer-events: none;

  /* 多层暗角叠加，模拟 exp(-dot(lighting, lighting)) 的指数衰减 */
  background:
    /* 外层强暗角 */
    radial-gradient(
      ellipse at center,
      transparent 50%,
      rgba(0, 0, 0, 0.15) 70%,
      rgba(0, 0, 0, 0.5) 85%,
      rgba(0, 0, 0, 0.85) 100%
    );

  /* 额外的内阴影增强边缘深度 */
  box-shadow:
    inset 0 0 120px 40px rgba(0, 0, 0, 0.5),
    inset 0 0 30px 10px rgba(0, 0, 0, 0.3);
  border-radius: 18px;
}

/* === 屏幕玻璃反光 === */
.crt-reflection {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 5;
  pointer-events: none;
  border-radius: 18px;

  /* 模拟CRT玻璃表面的光线反射 - 左上角到右下角的高光带 */
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.04) 0%,
    rgba(255, 255, 255, 0.01) 30%,
    transparent 50%,
    transparent 100%
  );
}

/* === 屏幕闪烁效果 (Flicker) === */
/*
 * 模拟CRT显示器的轻微亮度波动
 * 这是由于老式CRT的电源和电子束稳定性不足导致的
 */
.crt-flicker {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 6;
  pointer-events: none;
  background: rgba(18, 16, 16, 0.1);
  opacity: 0;
  animation: crt-flicker 0.15s infinite;
}

@keyframes crt-flicker {
  0% { opacity: 0.028; }
  5% { opacity: 0.035; }
  10% { opacity: 0.024; }
  15% { opacity: 0.045; }
  20% { opacity: 0.018; }
  25% { opacity: 0.042; }
  30% { opacity: 0.033; }
  35% { opacity: 0.034; }
  40% { opacity: 0.027; }
  45% { opacity: 0.042; }
  50% { opacity: 0.048; }
  55% { opacity: 0.009; }
  60% { opacity: 0.020; }
  65% { opacity: 0.036; }
  70% { opacity: 0.027; }
  75% { opacity: 0.019; }
  80% { opacity: 0.036; }
  85% { opacity: 0.035; }
  90% { opacity: 0.035; }
  95% { opacity: 0.018; }
  100% { opacity: 0.024; }
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
