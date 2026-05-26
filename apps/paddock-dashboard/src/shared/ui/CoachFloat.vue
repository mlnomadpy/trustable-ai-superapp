<script setup lang="ts">
import { computed } from 'vue'
import DialogueBox from '@/widgets/dialogue-box/DialogueBox.vue'
import { useSaveStore } from '@/entities/save/model/saveStore'

interface Props {
  emotion: string
  text: string
  coachId?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'done'): void
}>()

const save = useSaveStore()

const resolvedCoachId = computed(() => {
  return props.coachId ?? save.activeSlot?.preferredCoach ?? 'trod'
})
</script>

<template>
  <div class="coach-float">
    <DialogueBox
      :coach-id="resolvedCoachId"
      :emotion="emotion"
      :text="text"
      compact
      @done="$emit('done')"
    />
  </div>
</template>

<style scoped>
.coach-float {
  position: absolute;
  bottom: clamp(20px, 5vh, 40px);
  left: clamp(8px, 2vw, 16px);
  right: clamp(8px, 2vw, 16px);
  /* Sits above the GarageHub spatial-item stack (which uses z-index 10) so
     the welcome dialogue never gets covered by a focused / next tile that
     translates toward the camera. */
  z-index: 100;
  pointer-events: none; /* Pass through — dialogue-layout handles its own clicks */
}
</style>
