<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import PageShell from '@/shared/ui/PageShell.vue'

import WelcomeStep from './steps/WelcomeStep.vue'
import NameEntry from './steps/NameEntry.vue'
import AvatarSelect from './steps/AvatarSelect.vue'
import SkillSelect from './steps/SkillSelect.vue'

const router = useRouter()
const route = useRoute()
const save = useSaveStore()
const audio = useAudioStore()

const currentStep = computed(() => parseInt(route.params.step as string) || 1)
const totalSteps = 4 

import { watch, onMounted } from 'vue'

const validateStep = () => {
  if (currentStep.value < 1 || currentStep.value > totalSteps) {
    router.replace('/onboarding/1')
  }
}

onMounted(validateStep)
watch(currentStep, validateStep) 

const pendingSave = ref({
  name: '',
  avatar: 'avatar_a',
  skill: 'beginner'
})

const goNext = async () => {
  if (currentStep.value < totalSteps) {
    router.push(`/onboarding/${currentStep.value + 1}`)
  } else {
    await commitSave()
    router.push('/garage')
  }
}

const goBack = () => {
  if (currentStep.value > 1) {
    router.push(`/onboarding/${currentStep.value - 1}`)
  } else {
    save.activeSlotId = null
    router.push('/save')
  }
}

const commitSave = async () => {
  if (!save.activeSlotId) return
  
  save.slots[save.activeSlotId - 1] = {
    schemaVersion: 1,
    id: save.activeSlotId,
    createdAt: new Date().toISOString(),
    lastPlayedAt: new Date().toISOString(),
    driverName: pendingSave.value.name,
    driverAvatar: pendingSave.value.avatar,
    skillLevel: pendingSave.value.skill as 'beginner' | 'intermediate' | 'pro',
    // No car preset — the driver picks one in the Pit Stall. Hardcoding
    // "BMW M3 (E46)" was a lie when the user hadn't selected anything.
    car: null,
    avatarSlot: 1,
    preferredCoach: 'trod',
    preferredTrack: 'sonoma',
    level: 1,
    sessions: [],
    bestLapBySession: {},
    coachAffinity: { trod: 1, bentley: 0, drill: 0, calm: 0, buddy: 0 },
    unlockedTracks: ['sonoma'],
    unlockedAvatars: [1],
    // All coaches are available from day one (per user request 2026-05-13);
    // `unlockedCoaches` is preserved on the save shape for future modes.
    unlockedCoaches: ['trod', 'buddy', 'drill', 'bentley', 'calm'],
    medals: [],
    goalsHistory: [],
    settings: {
      audio: { masterVolume: 80, musicVolume: 50, sfxVolume: 100, voiceVolume: 100, coachMute: false },
      display: { nightMode: false, reducedMotion: false, showFps: false },
      controls: { keyboardLayout: 'arrows', swapAB: false },
      ux: { typewriterSpeed: 'normal', hapticFeedback: true }
    }

  }
  
  await save.save()
  audio.playSfx('level_up')
}

const hints = computed(() => {
  if (currentStep.value === 1) return ['A · ADVANCE', '', '']
  if (currentStep.value === 2) return ['A · INSERT', 'B · BACK', 'END · CONFIRM']
  if (currentStep.value === 3) return ['◀ ▶ SELECT', 'B · BACK', 'A · CONFIRM']
  if (currentStep.value === 4) return ['A · SELECT', 'B · BACK', '▲ ▼ MOVE']
  return []
})
</script>

<template>
  <PageShell title="SETUP" :hints="hints" bg="neutral" :show-heading="false">
    <!-- Background overrides -->
    <div class="onboard-bg absolute inset-0 z-0 pointer-events-none"></div>
    
    <!-- Step indicator navbar -->
    <div class="step-bar">
      <div class="step-bar-inner">
        <span class="step-label">SET UP YOUR DRIVER</span>
        <span class="step-separator">·</span>
        <span class="step-count">
          <span v-for="i in totalSteps" :key="`step-${i}`" class="mr-[2px]" :class="i <= currentStep ? 'text-ui-info' : 'text-slate'">●</span>
        </span>
      </div>
      <!-- Progress bar -->
      <div class="step-progress">
        <div class="step-progress-fill" :style="{ width: `${(currentStep / totalSteps) * 100}%` }"></div>
      </div>
    </div>
    
    <!-- Content area -->
    <div class="content relative z-10">
      <WelcomeStep v-if="currentStep === 1" @next="goNext" />
      <NameEntry v-else-if="currentStep === 2" :initial-name="pendingSave.name" @update:name="pendingSave.name = $event" @next="goNext" @back="goBack" />
      <AvatarSelect v-else-if="currentStep === 3" :initial-avatar="pendingSave.avatar" @update:avatar="pendingSave.avatar = $event" @next="goNext" @back="goBack" />
      <SkillSelect v-else-if="currentStep === 4" :initial-skill="pendingSave.skill" @update:skill="pendingSave.skill = $event" @next="goNext" @back="goBack" />
    </div>
  </PageShell>
</template>

<style scoped>
.onboard-bg {
  background: linear-gradient(
    180deg,
    var(--color-ink) 0%,
    var(--color-asphalt-deep) 50%,
    var(--color-ink) 100%
  );
}

.step-bar {
  position: absolute;
  top: clamp(26px, 5vh, 48px); /* below StatusBar */
  left: 0;
  width: 100%;
  z-index: 10;
  background: rgba(26, 29, 46, 0.9);
  border-bottom: 1px solid var(--color-slate);
}

.step-bar-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(6px, 1.5vw, 14px);
  padding: clamp(4px, 1vh, 10px) clamp(8px, 2vw, 20px);
}

.step-label {
  font-size: clamp(10px, 2.5vmin, 20px);
  color: var(--color-silver);
  letter-spacing: 0.1em;
}

.step-separator {
  color: var(--color-slate);
}

.step-count {
  font-size: clamp(10px, 2.5vmin, 20px);
  color: var(--color-ui-info);
  font-weight: bold;
}

.step-progress {
  height: 2px;
  background: var(--color-slate);
}

.step-progress-fill {
  height: 100%;
  background: var(--color-ui-good);
  transition: width 0.3s steps(4);
  box-shadow: 0 0 6px rgba(42, 161, 152, 0.4);
}

.content {
  position: absolute;
  top: calc(clamp(26px, 5vh, 48px) + clamp(30px, 6vh, 52px)); /* StatusBar + step-bar */
  bottom: clamp(24px, 4.5vh, 44px); /* HintBar */
  left: 0;
  right: 0;
  overflow: hidden;
}
</style>
