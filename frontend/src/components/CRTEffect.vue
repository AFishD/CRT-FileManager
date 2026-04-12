<template>
  <div class="crt-monitor">
    <!-- CRT显示器外壳 -->
    <div class="crt-bezel">
      <!-- CRT屏幕玻璃 -->
      <div class="crt-screen" :class="{ 'crt-enabled': effectsEnabled }" :style="screenStyle">
        <!-- 内容层 -->
        <div class="crt-content" :style="contentStyle">
          <slot></slot>
        </div>

        <!-- 扫描线层 -->
        <div v-if="effectsEnabled" class="crt-scanlines" :style="scanlinesStyle"></div>

        <!-- RGB荫罩层 -->
        <div v-if="effectsEnabled && shadowMaskEnabled" class="crt-shadow-mask" :style="shadowMaskStyle"></div>

        <!-- 暗角层 -->
        <div v-if="effectsEnabled" class="crt-vignette" :style="vignetteStyle"></div>

        <!-- 反光层 -->
        <div v-if="effectsEnabled" class="crt-reflection"></div>

        <!-- 闪烁层 -->
        <div v-if="effectsEnabled && flickerEnabled" class="crt-flicker" :style="flickerStyle"></div>
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

const shadowMaskEnabled = computed(() => {
  return crtConfig.value.shadow_mask?.enabled ?? true;
});

const flickerEnabled = computed(() => {
  return crtConfig.value.flicker?.enabled ?? true;
});

// === 内容层样式：zoom + glow ===
const contentStyle = computed(() => {
  if (!effectsEnabled.value) return {};

  const glow = crtConfig.value.glow || {};
  const distortion = crtConfig.value.distortion || {};
  const blur = crtConfig.value.blur || {};

  const glowStrength = glow.strength || '1px';
  const glowColor = glow.color || 'rgba(255, 255, 255, 0.35)';
  const zoom = distortion.zoom ?? 1.02;
  const blurStrength = blur.strength || '0.3px';

  return {
    textShadow: `0 0 ${glowStrength} ${glowColor}`,
    transform: `scale(${zoom})`,
    filter: `blur(${blurStrength})`,
  };
});

// === 屏幕样式：mask 边缘渐隐受 distortion.strength 控制 ===
const screenStyle = computed(() => {
  if (!effectsEnabled.value) return {};

  const distortion = crtConfig.value.distortion || {};
  const strength = distortion.strength ?? 0.05;

  // strength 越大，mask 椭圆越小，边缘裁切越多
  const ellipseSize = Math.max(70, 98 - strength * 200); // 0.05 -> 88%, 0.2 -> 58%
  const solidStop = Math.max(30, 70 - strength * 200);   // 中心实区
  const borderRadius = Math.max(8, 10 + strength * 200);  // 圆角

  return {
    borderRadius: `${borderRadius}px`,
    WebkitMask: `radial-gradient(ellipse ${ellipseSize}% ${ellipseSize}% at 50% 50%, black ${solidStop}%, rgba(0,0,0,0.8) ${solidStop + 15}%, rgba(0,0,0,0.3) ${solidStop + 25}%, transparent 100%)`,
    mask: `radial-gradient(ellipse ${ellipseSize}% ${ellipseSize}% at 50% 50%, black ${solidStop}%, rgba(0,0,0,0.8) ${solidStop + 15}%, rgba(0,0,0,0.3) ${solidStop + 25}%, transparent 100%)`,
  };
});

// === 扫描线样式：opacity + spacing ===
const scanlinesStyle = computed(() => {
  const scanlines = crtConfig.value.scanlines || {};
  const opacity = scanlines.opacity ?? 0.3;
  const spacing = scanlines.spacing ?? 2;

  const halfSpacing = Math.floor(spacing / 2);
  const lineWidth = spacing - halfSpacing;

  return {
    backgroundImage: `repeating-linear-gradient(to bottom, transparent 0, transparent ${halfSpacing}px, rgba(0,0,0,${opacity}) ${halfSpacing}px, rgba(0,0,0,${opacity}) ${spacing}px)`,
    backgroundSize: `100% ${spacing}px`,
  };
});

// === 荫罩样式：opacity ===
const shadowMaskStyle = computed(() => {
  const shadowMask = crtConfig.value.shadow_mask || {};
  const opacity = shadowMask.opacity ?? 0.06;

  return {
    opacity: opacity,
  };
});

// === 暗角样式：strength ===
const vignetteStyle = computed(() => {
  const vignette = crtConfig.value.vignette || {};
  const strength = vignette.strength ?? 0.5;

  const innerAlpha = 0.15 * strength;
  const midAlpha = 0.5 * strength;
  const outerAlpha = 0.85 * strength;
  const shadowSize = Math.round(40 + 80 * strength);
  const shadowBlur = Math.round(120 + 80 * strength);
  const shadowAlpha = 0.5 * strength;

  return {
    background: `radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,${innerAlpha}) 70%, rgba(0,0,0,${midAlpha}) 85%, rgba(0,0,0,${outerAlpha}) 100%)`,
    boxShadow: `inset 0 0 ${shadowBlur}px ${shadowSize}px rgba(0,0,0,${shadowAlpha}), inset 0 0 30px 10px rgba(0,0,0,${shadowAlpha * 0.6})`,
  };
});

// === 闪烁样式：intensity 控制闪烁层的背景透明度 ===
const flickerStyle = computed(() => {
  const flicker = crtConfig.value.flicker || {};
  const intensity = flicker.intensity ?? 0.03;

  // intensity 映射到闪烁层背景的不透明度
  // 以及通过 CSS 自定义属性传递给动画
  // intensity=0.03 -> 微弱闪烁, intensity=0.5 -> 剧烈闪烁
  return {
    '--flicker-intensity': intensity,
    background: `rgba(18, 16, 16, ${Math.min(0.5, intensity * 3)})`,
  };
});
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

/* === 内容层 === */
.crt-content {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;
  transform-origin: center center;
}

/* === 扫描线 === */
.crt-scanlines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
  pointer-events: none;
  /* 扫描线是静态的，不做位移动画 */
}

/* === RGB荫罩 === */
.crt-shadow-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 3;
  pointer-events: none;
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
  /* opacity 通过 inline style 动态控制 */
}

/* === 暗角 === */
.crt-vignette {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 4;
  pointer-events: none;
  border-radius: 18px;
  /* background + box-shadow 通过 inline style 动态控制 */
}

/* === 反光 === */
.crt-reflection {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 5;
  pointer-events: none;
  border-radius: 18px;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.04) 0%,
    rgba(255, 255, 255, 0.01) 30%,
    transparent 50%,
    transparent 100%
  );
}

/* === 闪烁 === */
/*
 * 闪烁效果通过 CSS 自定义属性 --flicker-intensity 控制强度
 * background 也通过 inline style 动态设置
 *
 * intensity=0.03 -> 几乎不可见的微弱闪烁
 * intensity=0.1  -> 明显可见的闪烁
 * intensity=0.5  -> 剧烈闪烁（模拟老旧CRT）
 */
.crt-flicker {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 6;
  pointer-events: none;
  /* background 通过 inline style 设置，受 intensity 控制 */
  opacity: 0;
  animation: crt-flicker 0.15s infinite;
}

/*
 * 闪烁动画：随机的 opacity 波动
 * opacity 值已归一化到 0-1 范围，实际效果由 background 的 alpha 通道控制
 */
@keyframes crt-flicker {
  0% { opacity: 0.9; }
  5% { opacity: 1.0; }
  10% { opacity: 0.8; }
  15% { opacity: 1.0; }
  20% { opacity: 0.6; }
  25% { opacity: 1.0; }
  30% { opacity: 0.9; }
  35% { opacity: 1.0; }
  40% { opacity: 0.7; }
  45% { opacity: 1.0; }
  50% { opacity: 0.95; }
  55% { opacity: 0.3; }
  60% { opacity: 0.7; }
  65% { opacity: 1.0; }
  70% { opacity: 0.9; }
  75% { opacity: 0.6; }
  80% { opacity: 1.0; }
  85% { opacity: 0.95; }
  90% { opacity: 1.0; }
  95% { opacity: 0.6; }
  100% { opacity: 0.8; }
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
