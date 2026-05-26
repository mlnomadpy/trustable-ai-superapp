<script setup lang="ts">
/**
 * Standalone /garage/sponsors page wrapper. The actual list + detail UI
 * (and its keyboard handling) lives in `ui/SponsorContractsBody.vue` so
 * it can also render inside the QUEST LOG "SPONSORS" tab without
 * double-wrapping in PageShell.
 */
import PageShell from '@/shared/ui/PageShell.vue'
import SponsorContractsBody from './ui/SponsorContractsBody.vue'
</script>

<template>
  <PageShell title="SPONSORS" :hints="['B · BACK']" bg="warm">

    <template #heading>
      <div class="heading-block mb-[1.5vh]">
        <h1 class="text-title font-title text-gold-dark tracking-[0.2em] drop-shadow-[2px_2px_0_#ca8a04]">SPONSORS</h1>
        <div class="heading-rule bg-gold-dark"></div>
      </div>
    </template>

    <div class="flex-grow mx-2 pb-6 min-h-0">
      <!-- Sponsor backend not wired. Body renders an honest "FEATURE NOT
           IMPLEMENTED" panel — hints/title trimmed to match. -->
      <SponsorContractsBody :active="true" :owns-back-nav="true" />
    </div>
  </PageShell>
</template>
