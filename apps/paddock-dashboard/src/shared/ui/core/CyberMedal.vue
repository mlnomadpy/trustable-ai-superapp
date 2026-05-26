<script setup lang="ts">
/**
 * CyberMedal — Tier-specific medal SVG with distinct emblems.
 * Bronze=star, Silver=diamond, Gold=crown, Platinum=lightning, Rainbow=rings.
 * Reusable in MedalGrid, TrainerCard, Leaderboard, StageClear, etc.
 */
withDefaults(defineProps<{
  /** Medal tier */
  tier: 'BRONZE' | 'SILVER' | 'GOLD' | 'PLATINUM' | 'RAINBOW'
  /** Whether the medal is unlocked (visible) or locked (silhouette) */
  unlocked?: boolean
  /** Size override */
  size?: string
}>(), {
  unlocked: true,
  size: '100%',
})

const tierColors: Record<string, { fill: string; stroke: string; glow: string; accent: string }> = {
  BRONZE:   { fill: '#CD7F32', stroke: '#8B5E23', glow: 'rgba(205,127,50,0.4)',  accent: '#E8A858' },
  SILVER:   { fill: '#C0C0C0', stroke: '#808080', glow: 'rgba(192,192,192,0.4)', accent: '#E0E0E0' },
  GOLD:     { fill: '#FFD700', stroke: '#B8860B', glow: 'rgba(255,215,0,0.5)',   accent: '#FFF176' },
  PLATINUM: { fill: '#E5E4E2', stroke: '#9E9E9E', glow: 'rgba(229,228,226,0.5)', accent: '#FFFFFF' },
  RAINBOW:  { fill: '#FF69B4', stroke: '#C2185B', glow: 'rgba(255,105,180,0.5)', accent: '#E040FB' },
}

const c = (tier: string) => tierColors[tier] ?? tierColors.BRONZE
</script>

<template>
  <div class="cyber-medal" :style="{ width: size, height: size }">
    <!-- Unlocked medal -->
    <template v-if="unlocked">
      <svg class="medal-svg" :class="'shimmer-' + tier.toLowerCase()" viewBox="0 0 48 48" fill="none">
        <!-- Ribbon tails -->
        <path d="M18 30L14 44L19 40L22 46L24 32" :fill="c(tier).stroke" opacity="0.8"/>
        <path d="M30 30L34 44L29 40L26 46L24 32" :fill="c(tier).stroke" opacity="0.8"/>
        <!-- Medal circle -->
        <circle cx="24" cy="22" r="14" :fill="c(tier).fill" :stroke="c(tier).stroke" stroke-width="2"/>
        <circle cx="24" cy="22" r="10" fill="none" :stroke="c(tier).accent" stroke-width="1" opacity="0.6"/>

        <!-- Bronze: Star -->
        <template v-if="tier === 'BRONZE'">
          <polygon points="24,14 26.5,19.5 32,20 28,24 29,30 24,27 19,30 20,24 16,20 21.5,19.5" :fill="c(tier).accent" opacity="0.9"/>
        </template>
        <!-- Silver: Diamond -->
        <template v-else-if="tier === 'SILVER'">
          <polygon points="24,14 28,22 24,30 20,22" :fill="c(tier).accent" opacity="0.8"/>
          <polygon points="24,16 26,22 24,28 22,22" :fill="c(tier).stroke" opacity="0.4"/>
        </template>
        <!-- Gold: Crown -->
        <template v-else-if="tier === 'GOLD'">
          <path d="M17,27 L17,20 L21,24 L24,17 L27,24 L31,20 L31,27 Z" :fill="c(tier).accent" opacity="0.9"/>
          <rect x="17" y="26" width="14" height="2" rx="0.5" :fill="c(tier).stroke" opacity="0.6"/>
        </template>
        <!-- Platinum: Lightning -->
        <template v-else-if="tier === 'PLATINUM'">
          <polygon points="26,13 22,22 26,22 21,31 28,20 24,20" :fill="c(tier).accent" opacity="0.9"/>
        </template>
        <!-- Rainbow: Rings -->
        <template v-else-if="tier === 'RAINBOW'">
          <circle cx="21" cy="22" r="4" fill="none" stroke="#FF6B6B" stroke-width="1.5" opacity="0.9"/>
          <circle cx="27" cy="22" r="4" fill="none" stroke="#4ECDC4" stroke-width="1.5" opacity="0.9"/>
          <circle cx="24" cy="19" r="2" fill="#FFF176" opacity="0.8"/>
        </template>

        <!-- Shine -->
        <ellipse cx="20" cy="17" rx="4" ry="3" fill="white" opacity="0.15" transform="rotate(-20 20 17)"/>
      </svg>
      <div class="medal-glow" :style="{ background: `radial-gradient(circle at center, ${c(tier).glow} 0%, transparent 70%)` }"></div>
    </template>

    <!-- Locked medal -->
    <template v-else>
      <svg class="lock-svg" viewBox="0 0 48 48" fill="none">
        <circle cx="24" cy="22" r="14" fill="none" stroke="var(--color-slate)" stroke-width="1.5" stroke-dasharray="3 3" opacity="0.4"/>
        <circle cx="24" cy="22" r="10" fill="none" stroke="var(--color-slate)" stroke-width="1" stroke-dasharray="2 2" opacity="0.2"/>
        <rect x="20" y="22" width="8" height="7" rx="1" fill="var(--color-slate)" opacity="0.5"/>
        <path d="M22 22V19a2 2 0 0 1 4 0v3" fill="none" stroke="var(--color-slate)" stroke-width="1.5" opacity="0.5"/>
      </svg>
    </template>
  </div>
</template>

<style scoped>
.cyber-medal {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.medal-svg {
  width: 80%;
  height: 80%;
  filter: drop-shadow(1px 2px 2px rgba(0, 0, 0, 0.5));
  z-index: 2;
  position: relative;
}

.shimmer-gold,
.shimmer-platinum,
.shimmer-rainbow {
  animation: medal-shimmer 3s ease-in-out infinite;
}

.shimmer-rainbow {
  filter: drop-shadow(1px 2px 2px rgba(0, 0, 0, 0.5)) 
          drop-shadow(0 0 4px rgba(255, 105, 180, 0.4));
}

.medal-glow {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
}

.lock-svg {
  width: 60%;
  height: 60%;
  opacity: 0.6;
}

@keyframes medal-shimmer {
  0%, 100% { filter: drop-shadow(1px 2px 2px rgba(0,0,0,0.5)) brightness(1); }
  50% { filter: drop-shadow(1px 2px 2px rgba(0,0,0,0.5)) brightness(1.15); }
}

@media (prefers-reduced-motion: reduce) {
  .shimmer-gold, .shimmer-platinum, .shimmer-rainbow { animation: none; }
}
</style>
