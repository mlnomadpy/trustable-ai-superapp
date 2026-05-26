<script setup lang="ts">
/**
 * Thin Chart.js wrapper tuned for the Pitwall dark theme. Mirrors the
 * `lineOpts(...)` helper in docs/telemetry-viewer.html — ticks #9aa0b4,
 * tooltip #15151c bg, scanline-friendly transparent grid. Optional
 * zoom plugin via the `zoom` prop.
 *
 * The chart instance is created lazily on mount, destroyed on unmount
 * (prevents the canvas/Chart leak we fixed in PR-B), and recreated
 * when `data`/`options` change since Chart.js doesn't deeply diff
 * scale config.
 */
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import type {
  Chart as ChartT,
  ChartConfiguration,
  ChartData,
  ChartOptions,
} from 'chart.js'

interface Props {
  data: ChartData<'line' | 'scatter'>
  /** Extra options merged over the dark-theme defaults. */
  options?: ChartOptions<'line' | 'scatter'>
  /** Enable wheel/pinch zoom + drag pan via chartjs-plugin-zoom. */
  zoom?: boolean
  /** scatter = 'scatter', otherwise 'line'. */
  type?: 'line' | 'scatter'
  /** Forwarded ARIA label for the canvas. */
  ariaLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  zoom: false,
  type: 'line',
  ariaLabel: 'chart',
})

const canvasRef = ref<HTMLCanvasElement | null>(null)
const chart = shallowRef<ChartT<'line' | 'scatter'> | null>(null)
let zoomRegistered = false

function darkBase(extra: ChartOptions<'line' | 'scatter'> = {}, enableZoom = false) {
  const plugins: Record<string, unknown> = {
    legend: { labels: { color: '#9aa0b4', boxWidth: 10, boxHeight: 1, font: { size: 11 } } },
    tooltip: {
      backgroundColor: '#15151c',
      titleColor: '#e9e9f0',
      bodyColor: '#e9e9f0',
      borderColor: '#262635',
      borderWidth: 1,
    },
  }
  if (enableZoom) {
    plugins.zoom = {
      pan: { enabled: true, mode: 'x', modifierKey: undefined },
      zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
      limits: { x: { minRange: 0.05 } },
    }
  }
  const baseScales: Record<string, unknown> = {
    x: { ticks: { color: '#9aa0b4', maxRotation: 0 }, grid: { color: 'rgba(255,255,255,.04)' } },
    y: { ticks: { color: '#9aa0b4' }, grid: { color: 'rgba(255,255,255,.04)' } },
  }
  const merged: ChartOptions<'line' | 'scatter'> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { intersect: false, mode: 'index' },
    plugins,
    elements: { line: { tension: 0.05 } },
    ...extra,
  }
  // Deep-ish scale merge so callers can extend per-axis without
  // losing the dark tick/grid defaults.
  const scales: Record<string, unknown> = { ...baseScales }
  const incoming = (extra as { scales?: Record<string, unknown> }).scales
  if (incoming) {
    for (const [k, v] of Object.entries(incoming)) {
      scales[k] = { ...(baseScales[k] as object | undefined ?? {}), ...(v as object) }
    }
  }
  ;(merged as { scales?: Record<string, unknown> }).scales = scales
  return merged
}

async function build() {
  if (!canvasRef.value) return
  const { Chart, registerables } = await import('chart.js')
  if (!(Chart as unknown as { __pitwallRegistered?: boolean }).__pitwallRegistered) {
    Chart.register(...registerables)
    ;(Chart as unknown as { __pitwallRegistered?: boolean }).__pitwallRegistered = true
  }
  if (props.zoom && !zoomRegistered) {
    const zoomMod = await import('chartjs-plugin-zoom')
    Chart.register(zoomMod.default)
    zoomRegistered = true
  }
  destroy()
  const config: ChartConfiguration<'line' | 'scatter'> = {
    type: props.type,
    data: props.data,
    options: darkBase(props.options ?? {}, props.zoom),
  }
  chart.value = new Chart(canvasRef.value, config) as unknown as ChartT<'line' | 'scatter'>
}

function destroy() {
  if (chart.value) {
    chart.value.destroy()
    chart.value = null
  }
}

defineExpose({
  /** Reset zoom — only meaningful when `zoom` prop was true. */
  resetZoom() {
    // chartjs-plugin-zoom augments the instance with .resetZoom()
    ;(chart.value as unknown as { resetZoom?: () => void } | null)?.resetZoom?.()
  },
})

onMounted(build)
onUnmounted(destroy)

// Recreate when either data or options change. We could in theory
// patch in-place via chart.update(), but our datasets often swap
// scale configs (e.g. when picking a new signal set) and Chart.js
// doesn't always pick that up cleanly. Recreate is the safe path.
watch(() => [props.data, props.options, props.zoom, props.type], () => {
  void build()
}, { deep: true })
</script>

<template>
  <div class="cyber-line-chart">
    <canvas ref="canvasRef" :aria-label="ariaLabel" role="img" />
  </div>
</template>

<style scoped>
.cyber-line-chart {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
}
canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
}
</style>
