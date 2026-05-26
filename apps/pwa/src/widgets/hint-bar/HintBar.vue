<script setup lang="ts">
import { onMounted, watchEffect } from 'vue'

export interface HintAction {
  /** Display label (e.g., "BACK", "SELECT", "COMPARE") */
  label: string
  /** The keyboard key this originally mapped to (for dispatching) */
  key?: string
  /** Display text for the key (e.g., "A", "B", "◆") */
  keyLabel?: string
  /** Optional icon character (e.g., "◀", "▶") */
  icon?: string
  /** Visual style */
  variant?: 'default' | 'primary' | 'warn' | 'subtle'
}

const props = defineProps<{ 
  /** Legacy string hints for backward compatibility */
  hints?: string[]
  /** New structured actions */
  actions?: HintAction[]
}>()

const emit = defineEmits<{
  (e: 'action', action: HintAction): void
}>()

/** Parse legacy hint strings like "A · SELECT" into HintAction objects */
const parsedActions = (): HintAction[] => {
  if (props.actions && props.actions.length > 0) return props.actions
  if (!props.hints) return []

  return props.hints.map(hint => {
    // Pattern: "KEY · LABEL" or just "LABEL"
    const parts = hint.split(' · ')
    if (parts.length >= 2) {
      const keyPart = parts[0].trim()
      const labelPart = parts.slice(1).join(' · ').trim()
      
      // Determine the key to dispatch
      const keyMap: Record<string, string> = {
        'A': 'Enter',
        'B': 'Escape',
        'C': 'c',
        'D': 'd',
        '◆': 'Shift',
        '◀ ▶': '',      // directional, not a single action
        '▲ ▼': '',      // directional, not a single action
        '▲ ▼ ◀ ▶': '',  // directional, not a single action
        'SHIFT+◀ ▶': '',
        'SPACE': ' ',
      }

      const mappedKey = keyMap[keyPart] ?? keyPart.toLowerCase()
      
      // Directional hints are informational only
      const isDirectional = !mappedKey
      
      // Determine variant
      let variant: HintAction['variant'] = 'default'
      if (keyPart === 'A' || keyPart === 'ENTER') variant = 'primary'
      if (keyPart === 'B') variant = 'warn'
      if (isDirectional) variant = 'subtle'

      return {
        label: labelPart,
        key: isDirectional ? undefined : mappedKey,
        keyLabel: keyPart,
        icon: isDirectional ? keyPart : undefined,
        variant,
      }
    }
    return { label: hint, variant: 'subtle' as const }
  })
}

// ── Dev-time sanity check ────────────────────────────────────────────────
// Warn when the parent page binds a keyboard shortcut via `useKeyboard()`
// that isn't represented in the HintBar's hints/actions. Today
// `useKeyboard` is a fire-and-forget stack — it does not maintain a
// per-handler registry of which keys the handler matches against — so we
// can't reliably introspect bindings. Until that lands, this hook is a
// stub that documents the future contract.
//
// TODO: wire when useKeyboard tracks bindings — expected shape would be
// `useKeyboard.getActiveBindings(): string[]`, against which we'd diff
// `parsedActions().map(a => a.key).filter(Boolean)`.
if (import.meta.env.DEV) {
  onMounted(() => {
    watchEffect(() => {
      const declared = parsedActions()
        .map(a => a.key)
        .filter((k): k is string => !!k)
      // No-op until useKeyboard exposes a binding registry. Reading
      // `declared` keeps watchEffect happy and ensures the dev-only branch
      // is exercised (tree-shaken out of prod builds).
      void declared
    })
  })
}

const handleTap = (action: HintAction) => {
  if (!action.key) return // Directional hints are not tappable
  
  // Dispatch the corresponding keyboard event so existing handlers fire
  const syntheticEvent = new KeyboardEvent('keydown', {
    key: action.key, 
    bubbles: true 
  }) as KeyboardEvent & { __pitwallHintTap?: boolean }

  syntheticEvent.__pitwallHintTap = true
  window.dispatchEvent(syntheticEvent)

  emit('action', action)
}
</script>

<template>
  <div class="hint-bar pixelated" role="toolbar" aria-label="Actions">
    <div class="hints-inner no-scrollbar">
      <button 
        v-for="(action, index) in parsedActions()" 
        :key="index" 
        class="hint-btn"
        :class="[
          `variant-${action.variant || 'default'}`,
          { tappable: !!action.key }
        ]"
        :aria-label="action.label"
        :disabled="!action.key"
        @click="handleTap(action)"
      >
        <span v-if="action.keyLabel && !action.icon" class="keycap" aria-hidden="true">{{ action.keyLabel }}</span>
        <span v-if="action.icon" class="hint-icon" aria-hidden="true">{{ action.icon }}</span>
        <span class="hint-label font-bold">{{ action.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.hint-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: calc(var(--safe-bottom) + 38px);
  background: linear-gradient(180deg, rgba(26, 29, 46, 0.85) 0%, rgba(26, 29, 46, 0.95) 100%);
  display: flex;
  align-items: flex-start; /* Align to top of bar, safe area handles bottom */
  justify-content: center;
  padding: 4px calc(var(--safe-right) + var(--space-sm)) 0 calc(var(--safe-left) + var(--space-sm));
  font-family: var(--font-ui);
  font-size: clamp(10px, calc(2vmin * var(--app-scale)), 18px);
  border-top: 1px solid var(--color-slate);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.3);
  z-index: var(--z-sticky);
  color: var(--color-silver);
}


.hints-inner {
  display: flex;
  align-items: center;
  gap: clamp(4px, 1vw, 12px);
  width: 100%;
  overflow: hidden;
  flex-wrap: nowrap;
  justify-content: center;
}

.hint-btn {
  display: flex;
  align-items: center;
  gap: clamp(4px, 0.6vw, 8px);
  white-space: nowrap;
  flex-shrink: 1;
  min-width: 0;
  background: none;
  border: 1px solid transparent;
  outline: none;
  cursor: default;
  font: inherit;
  color: inherit;
  padding: clamp(3px, 0.6vh, 6px) clamp(6px, 1.5vw, 12px);
  transition: all var(--duration-fast, 150ms) ease;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  -webkit-user-select: none;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Tappable buttons get interactive styles */
.hint-btn.tappable {
  cursor: pointer;
  border-color: color-mix(in srgb, var(--color-slate) 40%, transparent);
  border-radius: 4px;
  flex-shrink: 0; /* Tappable buttons should stay visible */
  background: color-mix(in srgb, var(--color-charcoal) 50%, transparent);
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.hint-btn.tappable:active {
  transform: scale(0.95);
  box-shadow: none;
}

.hint-btn.tappable:focus-visible {
  box-shadow: var(--shadow-focus);
}

/* Keycap Styling */
.keycap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.6em;
  height: 1.6em;
  padding: 0 4px;
  background: var(--color-charcoal);
  border: 1px solid currentColor;
  border-bottom-width: 2px;
  border-radius: 50%;
  font-weight: 900;
  font-size: 0.9em;
  box-shadow: inset 0 2px 0 rgba(255,255,255,0.1);
  text-shadow: none;
}

.hint-btn:active .keycap {
  border-bottom-width: 1px;
  transform: translateY(1px);
}

/* Variants */
.variant-primary {
  color: var(--color-ui-good);
}
.variant-primary.tappable {
  border-color: color-mix(in srgb, var(--color-ui-good) 40%, transparent);
  background: color-mix(in srgb, var(--color-ui-good) 10%, transparent);
}

.variant-warn {
  color: var(--color-ui-warn);
}
.variant-warn.tappable {
  border-color: color-mix(in srgb, var(--color-ui-warn) 40%, transparent);
  background: color-mix(in srgb, var(--color-ui-warn) 10%, transparent);
}

.variant-default {
  color: var(--color-silver);
}

.variant-subtle {
  color: var(--color-slate);
  opacity: 0.7;
  font-size: 0.9em;
  flex-shrink: 1; /* Subtle hints shrink first */
}

.variant-subtle .keycap {
  border-radius: 4px;
  border: 1px solid var(--color-slate);
  background: transparent;
  color: var(--color-slate);
  box-shadow: none;
}

.hint-icon {
  opacity: 0.7;
  font-size: 0.9em;
}

.hint-label {
  letter-spacing: 0.05em;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
