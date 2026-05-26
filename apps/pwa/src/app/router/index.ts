import { createRouter, createWebHistory } from 'vue-router'
import { useTransitionStore } from '@/shared/lib/transition/transitionStore'
import { useSaveStore } from '@/entities/save/model/saveStore'
import type { TransitionDirection } from '@/shared/lib/transition/transitionStore'

// Import page components using FSD paths
// TitleScreen is eagerly loaded (first paint); all others are lazy-loaded to reduce initial bundle
import TitleScreen from '@/pages/home/TitleScreen.vue'

const routes = [
  { path: '/', name: 'title', component: TitleScreen },
  { path: '/save', name: 'save', component: () => import('@/pages/save-select/SaveSelect.vue'), meta: { wipe: 'right' } },
  { path: '/onboarding/:step', name: 'onboarding', component: () => import('@/pages/onboarding/OnboardingFlow.vue'), meta: { wipe: 'right' } },
  { path: '/garage', name: 'garage', component: () => import('@/pages/garage-hub/GarageHub.vue'), meta: { wipe: 'right', requiresSave: true } },
  { path: '/garage/setup', name: 'car-setup', component: () => import('@/pages/garage-hub/CarSetup.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/garage/trainer', name: 'trainer-card', component: () => import('@/pages/trainer-card/TrainerCard.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/garage/coach', name: 'coach-select', component: () => import('@/pages/coach-select/CoachSelect.vue'), meta: { wipe: 'left', requiresSave: true } },
  { path: '/garage/coach/bios', name: 'coach-bios', component: () => import('@/pages/coach-select/CoachBios.vue'), meta: { wipe: 'down', requiresSave: true } },
  { path: '/garage/pit-stall', name: 'pit-stall', component: () => import('@/pages/pit-stall/PitStall.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/garage/pit-stall/hardware', name: 'hardware', component: () => import('@/pages/hardware-detail/HardwareDetail.vue'), meta: { wipe: 'left', requiresSave: true } },
  { path: '/pit-stall/live', name: 'pit-stall-live', component: () => import('@/pages/pit-stall/LivePitWall.vue'), meta: { wipe: 'down', requiresSave: true } },
  { path: '/garage/quests', name: 'quests', component: () => import('@/pages/quest-log/QuestLog.vue'), meta: { wipe: 'down', requiresSave: true } },
  { path: '/garage/sponsors', name: 'sponsors', component: () => import('@/pages/quest-log/SponsorContracts.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/garage/analysis', name: 'analysis', component: () => import('@/pages/analysis-hub/AnalysisHub.vue'), meta: { wipe: 'left', requiresSave: true } },
  { path: '/analysis/lap-times', name: 'lap-times', component: () => import('@/pages/lap-times-hall/LapTimesHall.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/analysis/compare', name: 'compare', component: () => import('@/pages/comparison-view/ComparisonView.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/analysis/corners', name: 'corners', component: () => import('@/pages/corner-mastery/CornerMastery.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/analysis/straights', name: 'straights', component: () => import('@/pages/straights-and-speed/StraightsAndSpeed.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/analysis/track', name: 'track', component: () => import('@/pages/track-walk/TrackWalk.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/analysis/atlas', name: 'atlas', component: () => import('@/pages/track-atlas/TrackAtlas.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/analysis/evolution', name: 'evolution', component: () => import('@/pages/driver-evolution/DriverEvolution.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/analysis/pedals', name: 'pedals', component: () => import('@/pages/pedal-profile/PedalProfile.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/analysis/ghosts', name: 'ghosts', component: () => import('@/pages/analysis-hub/GhostManager.vue'), meta: { wipe: 'down', requiresSave: true } },
  { path: '/analysis/replay', name: 'replay', component: () => import('@/pages/analysis-hub/TelemetryReplay.vue'), meta: { wipe: 'left', requiresSave: true } },
  { path: '/analysis/sql', name: 'sql', component: () => import('@/pages/sql-console/SqlConsole.vue'), meta: { wipe: 'down', requiresSave: true } },
  { path: '/briefing', name: 'briefing', component: () => import('@/pages/pre-brief/PreBrief.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/hud', name: 'hud', component: () => import('@/pages/on-track-hud/OnTrackHud.vue'), meta: { wipe: 'down', requiresSave: true, performance: true, allowPause: true } },
  { path: '/stage-clear', name: 'stage-clear', component: () => import('@/pages/stage-clear/StageClear.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/calibration', name: 'calibration', component: () => import('@/pages/calibration/Calibration.vue'), meta: { wipe: 'down', requiresSave: true } },
  { path: '/notifications', name: 'notifications', component: () => import('@/pages/notifications/NotificationCenter.vue'), meta: { wipe: 'up', requiresSave: true } },
  { path: '/settings', name: 'settings', component: () => import('@/pages/settings/Settings.vue'), meta: { wipe: 'down', requiresSave: true } },
  { path: '/end-of-day', name: 'end-of-day', component: () => import('@/pages/end-of-day/EndOfDay.vue'), meta: { wipe: 'down', requiresSave: true } },
  { path: '/leaderboard', name: 'leaderboard', component: () => import('@/pages/leaderboard/GlobalLeaderboard.vue'), meta: { wipe: 'left', requiresSave: true } },
  
  // Catch-all route to redirect back to title
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

export const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from) => {
  const save = useSaveStore()
  await save.hydrate()
  if (to.meta.requiresSave && save.activeSlotId === null) {
    return { name: 'title' } // No save -> back to title
  }
  
  const trans = useTransitionStore()
  const wipe = (to.meta.wipe ?? 'right') as TransitionDirection
  if (wipe && from.name !== undefined) {
    // Add a 2s timeout fallback so navigation never hangs if animation fails
    await Promise.race([
      trans.play(wipe),
      new Promise(resolve => setTimeout(resolve, 2000))
    ])
  }
  // Return true (or undefined) to allow navigation
})
