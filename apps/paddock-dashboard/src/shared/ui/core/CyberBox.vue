<script setup lang="ts">
interface Props {
  /** Background style */
  variant?: 'ink' | 'charcoal' | 'ghost' | 'glass'
  /** Border color */
  border?: 'slate' | 'silver' | 'primary' | 'good' | 'warn' | 'bad' | 'none'
  /** Enable hover/active states */
  interactive?: boolean
  /** Visual selected state */
  selected?: boolean
  /** Pass-through HTML role */
  role?: string
  /** Make focusable via keyboard */
  focusable?: boolean
}

withDefaults(defineProps<Props>(), {
  variant: 'charcoal',
  border: 'slate',
  interactive: false,
  selected: false,
  focusable: false,
})
</script>

<template>
  <div 
    class="cyber-box"
    :class="[
      variant === 'glass' ? 'bg-glass' : `bg-${variant}`, 
      `border-${border}`, 
      { interactive, selected, 'arcade-hover': interactive }
    ]"
    :role="role"
    :tabindex="focusable ? 0 : undefined"
  >
    <slot></slot>
  </div>
</template>

<style scoped>
.cyber-box {
  position: relative;
  display: flex;
  box-sizing: border-box;
  transition: all var(--duration-fast, 150ms) ease;
  border-width: 1px;
  border-style: solid;
}

/* Backgrounds */
.bg-ink { background: linear-gradient(135deg, rgba(20, 22, 36, 0.9) 0%, rgba(13, 14, 26, 0.95) 100%); }
.bg-charcoal { background: linear-gradient(135deg, rgba(38, 44, 62, 0.9) 0%, rgba(26, 29, 40, 0.95) 100%); }
.bg-ghost { background-color: transparent; }
.bg-glass { background: color-mix(in srgb, var(--color-ink) 85%, transparent); backdrop-filter: blur(4px); }

/* Borders */
.border-slate { border-color: var(--color-slate); }
.border-silver { border-color: var(--color-silver); }
.border-primary { border-color: var(--color-ui-info); }
.border-good { border-color: var(--color-ui-good); }
.border-warn { border-color: var(--color-ui-warn); }
.border-bad { border-color: var(--color-ui-bad); }
.border-none { border-color: transparent; border-width: 0; }

/* Interactive States */
.cyber-box.interactive {
  cursor: pointer;
}

.cyber-box:focus-visible {
  outline: 2px solid var(--color-ui-good);
  outline-offset: 2px;
}

/* Selected State */
.cyber-box.selected {
  border-color: var(--color-ui-good);
  background: linear-gradient(135deg, rgba(42, 161, 152, 0.15) 0%, rgba(26, 29, 40, 0.95) 100%);
  box-shadow: inset 0 0 12px rgba(78, 205, 196, 0.2), var(--shadow-glow-teal, 0 0 16px rgba(78, 205, 196, 0.3));
}
</style>
