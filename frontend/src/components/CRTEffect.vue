<template>
  <div class="crt-container">
    <!-- 模板被大大简化，不再需要SVG -->
    <div class="crt-content" :style="contentStyle">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
// script 部分也被大大简化
import { computed } from 'vue';

const props = defineProps({
  config: {
    type: Object,
    required: true
  }
});

const contentStyle = computed(() => {
  if (!props.config.crt_effects.enabled) {
    return {};
  }

  const effects = props.config.crt_effects;
  const distortion = effects.distortion || { zoom: 1.01 }; // 我们只保留 zoom
  
  return {
    // 滤镜现在只负责 blur，不再有 url()
    filter: `blur(${effects.blur.strength})`,
    textShadow: `0 0 ${effects.glow.strength} ${effects.glow.color}`,
    // transform 只负责缩放，不再需要 translateZ(0)
    transform: `scale(${distortion.zoom})`
  };
});
</script>

<style scoped>
.crt-container {
  width: 100vw;
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
  background: #000;
  overflow: hidden; 
}

.crt-content {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;

  /* 
    --- 核心实现 ---
    我们使用一个CSS Mask来将矩形的内容“裁剪”成一个椭圆形的CRT屏幕形状。
    - radial-gradient 创建了一个椭圆形的渐变。
    - ellipse 85% 100% 定义了椭圆的形状（水平略窄，垂直更高）。
    - black 65% 表示中心65%的区域是完全可见的。
    - transparent 100% 表示从65%到边缘会平滑地淡出至完全透明。
    这创造了一个非常自然的、边缘羽化的屏幕效果。
  */
  -webkit-mask: radial-gradient(ellipse 85% 100% at 50% 50%, black 65%, transparent 100%);
  mask: radial-gradient(ellipse 85% 100% at 50% 50%, black 65%, transparent 100%);
  
  /* 
    我们仍然保留这个伪元素，因为它创建的内阴影效果（暗角）
    与遮罩结合在一起，能极大地增强CRT的立体感和真实感。
  */
}

.crt-content::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  /* 我们甚至可以给这个阴影一个轻微的圆角来匹配遮罩的形状 */
  border-radius: 2% / 5%;
  box-shadow: inset 0 0 80px 40px rgba(0, 0, 0, 0.75);
  pointer-events: none;
  z-index: 2;
}
</style>