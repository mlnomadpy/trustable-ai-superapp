<script setup lang="ts">
/**
 * HudCornerTile — minimalist numeric tile for the cockpit HUD corners.
 *
 * Renders a small uppercase label above a large numeric value. Optional
 * unit + suffix slot. No frames, no borders — relies on contrast against
 * the dark cockpit background. Sized in `vmin` so it tracks the shorter
 * viewport axis cleanly on Pixel 10 landscape (1080 short side).
 */
defineProps<{
  label: string
  value: string | number
  unit?: string
  /** Visual tone for the value text. 'silver' is the cockpit default. */
  tone?: 'silver' | 'good' | 'warn' | 'bad' | 'muted'
  /** Right-align contents (use for the top-right tile). */
  align?: 'left' | 'right'
}>()
</script>

<template>
  <div
    class="corner-tile"
    :class="[`align-${align ?? 'left'}`]"
  >
    <span class="corner-label">{{ label }}</span>
    <span class="corner-value-row">
      <span class="corner-value" :class="`tone-${tone ?? 'silver'}`">{{ value }}</span>
      <span v-if="unit" class="corner-unit">{{ unit }}</span>
    </span>
    <slot name="below" />
  </div>
</template>

<style scoped>
.corner-tile {
  display: flex;
  flex-direction: column;
  gap: clamp(2px, 0.4vmin, 6px);
  min-width: 0;
}

.align-right {
  align-items: flex-end;
  text-align: right;
}

.corner-label {
  font-family: var(--font-ui);
  font-weight: 800;
  font-size: clamp(10px, 1.6vmin, 13px);
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--color-slate) 80%, transparent);
  line-height: 1;
}

.corner-value-row {
  display: inline-flex;
  align-items: baseline;
  gap: clamp(4px, 0.8vmin, 8px);
  line-height: 1;
}

.corner-value {
  font-family: var(--font-nums);
  font-weight: 900;
  font-size: clamp(28px, 5.5vmin, 56px);
  letter-spacing: -0.01em;
  line-height: 1;
}

.tone-silver { color: var(--color-silver); }
.tone-good   { color: var(--color-ui-good); }
.tone-warn   { color: var(--color-ui-warn); }
.tone-bad    { color: var(--color-ui-bad); }
.tone-muted  { color: color-mix(in srgb, var(--color-slate) 60%, transparent); }

.corner-unit {
  font-family: var(--font-ui);
  font-weight: 700;
  font-size: clamp(11px, 1.8vmin, 16px);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--color-slate) 70%, transparent);
}
</style>
