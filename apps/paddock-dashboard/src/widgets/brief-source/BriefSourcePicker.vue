<script setup lang="ts">
/**
 * BriefSourcePicker — choose which historical session the pre-brief
 * should be computed from. Defaults to "(auto)" which lets the bridge
 * pick based on the active session / driver profile.
 *
 * Emits `change` with the selected session_id (or null for auto).
 * Re-fetches the brief inside the parent on change.
 */
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { bridge } from '@/shared/api/bridge'

interface SessionSummary {
  session_id: string
  driver?: string | null
  track?: string | null
  car?: string | null
  started_at?: string | null
}

const props = defineProps<{
  /** Currently selected session id (null = auto). */
  modelValue?: string | null
  /** Disable the picker (e.g. while a fetch is in flight). */
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: string | null): void
  (e: 'change', v: string | null): void
}>()

const sessions = ref<SessionSummary[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const selected = ref<string | null>(props.modelValue ?? null)
let pollTimer: number | null = null

watch(() => props.modelValue, (v) => { selected.value = v ?? null })

async function refresh() {
  loading.value = true
  error.value = null
  try {
    const res = await bridge.get<{ sessions: SessionSummary[]; count?: number }>(
      '/sessions?limit=50'
    )
    sessions.value = (res.sessions || [])
      .filter((s) => s.session_id && s.session_id !== '_live')
      .sort((a, b) => (b.started_at || '').localeCompare(a.started_at || ''))
  } catch (e: any) {
    error.value = e?.message ?? String(e)
    sessions.value = []
  } finally {
    loading.value = false
  }
}

function onChange(ev: Event) {
  const v = (ev.target as HTMLSelectElement).value || null
  selected.value = v
  emit('update:modelValue', v)
  emit('change', v)
}

const fmt = (s: SessionSummary) => {
  const driver = s.driver || 'unknown'
  const track = s.track || ''
  const car = s.car || ''
  const when = s.started_at ? s.started_at.replace('T', ' ').slice(0, 16) : ''
  const meta = [track, car].filter(Boolean).join(' · ')
  return `${s.session_id} — ${driver}${meta ? ' · ' + meta : ''}${when ? ' · ' + when : ''}`
}

onMounted(() => {
  refresh()
  pollTimer = window.setInterval(refresh, 30_000)
})
onUnmounted(() => { if (pollTimer != null) window.clearInterval(pollTimer) })
</script>

<template>
  <div class="brief-source-picker text-body font-ui w-full">
    <div class="flex items-center gap-[clamp(4px,1vmin,8px)] flex-wrap w-full">
      <label class="text-silver tracking-widest text-small shrink-0">BRIEF BASIS</label>
      <select
        class="flex-1 bg-charcoal text-white border border-slate rounded px-2 text-small font-mono min-w-0 min-h-[44px] disabled:opacity-50 max-w-full"
        :value="selected ?? ''"
        :disabled="disabled || loading"
        @change="onChange"
        title="Pick a past session to base the brief on. (auto) defers to the active session."
      >
        <option value="">(auto — active session)</option>
        <option v-for="s in sessions" :key="s.session_id" :value="s.session_id">
          {{ fmt(s) }}
        </option>
      </select>
      <button
        class="text-silver hover:text-white border border-slate rounded px-3 text-body min-h-[44px] min-w-[44px] shrink-0"
        :disabled="loading"
        title="Re-fetch session list"
        aria-label="Refresh session list"
        @click="refresh"
      >↻</button>
    </div>
    <div v-if="loading" class="text-silver/70 text-small mt-1">loading sessions…</div>
    <div v-else-if="error" class="text-ui-bad text-small mt-1 break-words">{{ error }}</div>
    <div v-else-if="!sessions.length" class="text-silver/70 text-small mt-1">
      no past sessions found
    </div>
  </div>
</template>
