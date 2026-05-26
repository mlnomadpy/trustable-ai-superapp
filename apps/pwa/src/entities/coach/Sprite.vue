<script setup lang="ts">
import { computed } from 'vue'
import { useSpriteStore } from './model/spriteStore'

interface Props {
  sheet: 'trod' | 'bentley' | 'drill' | 'calm' | 'buddy' | 'avatars' | 'medals' | string
  animation: string
  scale?: number
  paused?: boolean
  /** Disable integer-scale snapping (default: snap on, for crisp pixel art) */
  smooth?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  scale: 1,
  paused: false,
  smooth: false,
})

const store = useSpriteStore()

// Pixel art blurs at non-integer upscale. When scale >= 1, snap to the
// nearest integer so we always sample on whole pixels. Sub-1 scales
// (e.g. tiny avatars in lists) pass through unchanged.
const effectiveScale = computed(() => {
  if (props.smooth) return props.scale
  if (props.scale < 1) return props.scale
  return Math.max(1, Math.round(props.scale))
})

const style = computed(() => {
  return store.cssFor(props.sheet, props.animation, {
    scale: effectiveScale.value,
    paused: props.paused
  })
})

const emit = defineEmits<{ (e: 'animationend'): void }>()

const onAnimEnd = () => {
  emit('animationend')
}
</script>

<template>
  <div
    :class="['sprite', `sprite-${sheet}`, `sprite-${animation}`]"
    :style="style"
    @animationend="onAnimEnd"
  ></div>
</template>

<style scoped>
.sprite {
  image-rendering: pixelated;
  background-repeat: no-repeat;
  /* width/height/animation/backgroundImage set inline via store.cssFor() */
}
</style>
