<script setup lang="ts">
interface Props {
  variant?: 'grid' | 'landscape' | 'stars'
  color?: 'default' | 'warm' | 'cool' | 'danger' | 'neutral'
}

withDefaults(defineProps<Props>(), {
  variant: 'grid',
  color: 'default'
})
</script>

<template>
  <div class="absolute inset-0 z-0 overflow-hidden select-none pointer-events-none">
    <!-- Grid Variant -->
    <div v-if="variant === 'grid'" 
         class="page-bg"
         :class="{
           'page-bg-warm': color === 'warm',
           'page-bg-cool': color === 'cool',
           'page-bg-danger': color === 'danger',
           'page-bg-neutral': color === 'neutral'
         }">
    </div>
    
    <!-- Stars Variant -->
    <div v-if="variant === 'stars'" class="stars-bg bg-ink w-full h-full">
      <div class="stars absolute inset-0"></div>
      <div class="stars stars-2 absolute inset-0"></div>
    </div>

    <!-- Landscape Variant -->
    <div v-if="variant === 'landscape'" class="landscape-bg w-full h-full relative">
      <div class="sky absolute inset-0"></div>
      <div class="stars absolute inset-0"></div>
      <div class="stars stars-2 absolute inset-0"></div>
      <div class="track-surface absolute bottom-0 left-0 w-full"></div>
      <div class="racing-stripe absolute bottom-0 left-0 w-full"></div>
      <div class="curb absolute"></div>
    </div>
  </div>
</template>

<style scoped>
/* =========================================
   GRID VARIANT
   ========================================= */
.page-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-color: var(--color-charcoal);
}

.page-bg::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: -50%;
  width: 200%;
  height: 100%;
  background-image: 
    linear-gradient(transparent 65%, rgba(78, 205, 196, 0.4) 66%, transparent 67%),
    linear-gradient(90deg, transparent 65%, rgba(78, 205, 196, 0.4) 66%, transparent 67%);
  background-size: 40px 40px;
  transform: perspective(600px) rotateX(60deg) translateY(100px);
  animation: grid-move 15s linear infinite;
  mask-image: linear-gradient(to top, black 20%, transparent 80%);
  -webkit-mask-image: linear-gradient(to top, black 20%, transparent 80%);
}

@keyframes grid-move {
  0% { transform: perspective(600px) rotateX(60deg) translateY(0); }
  100% { transform: perspective(600px) rotateX(60deg) translateY(40px); }
}

.page-bg-warm { background-color: #2a1f2d; }
.page-bg-warm::after { background-image:
  linear-gradient(transparent 65%, rgba(254, 202, 87, 0.3) 66%, transparent 67%),
  linear-gradient(90deg, transparent 65%, rgba(254, 202, 87, 0.3) 66%, transparent 67%); }

.page-bg-cool { background-color: #1a2233; }
.page-bg-cool::after { background-image:
  linear-gradient(transparent 65%, rgba(69, 183, 209, 0.3) 66%, transparent 67%),
  linear-gradient(90deg, transparent 65%, rgba(69, 183, 209, 0.3) 66%, transparent 67%); }

.page-bg-danger { background-color: #2d1a1a; }
.page-bg-danger::after { background-image:
  linear-gradient(transparent 65%, rgba(255, 71, 87, 0.3) 66%, transparent 67%),
  linear-gradient(90deg, transparent 65%, rgba(255, 71, 87, 0.3) 66%, transparent 67%); }

.page-bg-neutral { background-color: var(--color-charcoal); }
.page-bg-neutral::after {
  background-image: 
    linear-gradient(transparent 65%, rgba(255, 255, 255, 0.05) 66%, transparent 67%),
    linear-gradient(90deg, transparent 65%, rgba(255, 255, 255, 0.05) 66%, transparent 67%);
}

/* =========================================
   STARS VARIANT
   ========================================= */
.stars-bg {
  background: radial-gradient(circle at center, #1a1d3e 0%, #0d0e1a 100%);
}

.stars {
  background-image:
    radial-gradient(1px 1px at 10% 15%, rgba(255,255,255,0.7), transparent),
    radial-gradient(1px 1px at 25% 8%, rgba(255,255,255,0.5), transparent),
    radial-gradient(1.5px 1.5px at 40% 22%, rgba(255,255,255,0.8), transparent),
    radial-gradient(1px 1px at 55% 5%, rgba(255,255,255,0.4), transparent),
    radial-gradient(1px 1px at 70% 18%, rgba(255,255,255,0.6), transparent),
    radial-gradient(1.5px 1.5px at 85% 12%, rgba(255,255,255,0.7), transparent),
    radial-gradient(1px 1px at 15% 30%, rgba(255,255,255,0.3), transparent),
    radial-gradient(1px 1px at 60% 28%, rgba(255,255,255,0.5), transparent),
    radial-gradient(1px 1px at 92% 25%, rgba(255,255,255,0.4), transparent),
    radial-gradient(1px 1px at 35% 35%, rgba(255,255,255,0.3), transparent);
  animation: bg-twinkle 4s steps(4) infinite alternate;
}

.stars-2 {
  background-image:
    radial-gradient(1px 1px at 5% 20%, rgba(255,255,255,0.5), transparent),
    radial-gradient(1px 1px at 20% 32%, rgba(255,255,255,0.4), transparent),
    radial-gradient(1.5px 1.5px at 48% 10%, rgba(255,255,255,0.6), transparent),
    radial-gradient(1px 1px at 75% 28%, rgba(255,255,255,0.3), transparent),
    radial-gradient(1px 1px at 90% 8%, rgba(255,255,255,0.5), transparent),
    radial-gradient(1px 1px at 30% 5%, rgba(255,255,255,0.7), transparent),
    radial-gradient(1px 1px at 65% 15%, rgba(255,255,255,0.4), transparent);
  animation: bg-twinkle 5s steps(4) infinite alternate-reverse;
}

@keyframes bg-twinkle {
  0% { opacity: 0.4; }
  100% { opacity: 1; }
}

/* =========================================
   LANDSCAPE VARIANT
   ========================================= */
.sky {
  background: linear-gradient(
    180deg,
    #0d0e1a 0%,        /* deep night at top */
    #1a1d3e 25%,        /* sky-night */
    #3a2a4a 45%,        /* purple-dusk transition */
    #c8786a 65%,        /* sky-dusk — the warm horizon */
    #d8b878 78%,        /* sky-dawn — golden band */
    #2c3242 79%,        /* hard cut to asphalt */
    #1f2230 100%        /* asphalt-deep */
  );
}

.track-surface {
  height: 22vh;
  background: linear-gradient(180deg, #2c3242 0%, #1f2230 100%);
}

.racing-stripe {
  height: 22vh;
  background: repeating-linear-gradient(
    90deg,
    transparent 0,
    transparent 8vw,
    rgba(255,255,255,0.03) 8vw,
    rgba(255,255,255,0.03) 16vw
  );
}

.curb {
  bottom: 22vh;
  left: 0;
  width: 100%;
  height: clamp(4px, 1vh, 8px);
  background: repeating-linear-gradient(
    90deg,
    #c93838 0,
    #c93838 3vw,
    #f5f5e8 3vw,
    #f5f5e8 6vw
  );
}
</style>
