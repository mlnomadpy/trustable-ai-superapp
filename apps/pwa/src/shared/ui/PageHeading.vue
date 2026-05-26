<script setup lang="ts">
interface Props {
  title: string
  subtitle?: string
  align?: 'center' | 'left'
  showRule?: boolean
}

withDefaults(defineProps<Props>(), {
  align: 'center',
  showRule: true
})
</script>

<template>
  <div class="heading-block" :class="[`text-${align}`, align === 'left' ? 'text-left' : '']">
    <h1 class="text-title text-silver font-bold stagger-1">
      <slot>{{ title }}</slot>
    </h1>
    <span v-if="subtitle" class="text-body text-silver stagger-2">{{ subtitle }}</span>
    <div v-if="showRule" class="heading-rule"></div>
  </div>
</template>
