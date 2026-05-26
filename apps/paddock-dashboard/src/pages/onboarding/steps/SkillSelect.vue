<script setup lang="ts">
import { ref } from 'vue'
import CyberMenuList from '@/shared/ui/core/CyberMenuList.vue'
import DialogueBox from '@/widgets/dialogue-box/DialogueBox.vue'

const props = defineProps<{
  initialSkill: string
}>()

const emit = defineEmits<{ (e: 'next'): void; (e: 'back'): void; (e: 'update:skill', val: string): void }>()

const skills = [
  { id: 'beginner', label: 'BEGINNER', desc: '"We\'ll start from the absolute basics."' },
  { id: 'intermediate', label: 'INTERMEDIATE', desc: '"You know the racing line. Let\'s find time."' },
  { id: 'pro', label: 'PRO', desc: '"We are chasing tenths. No mercy."' },
]

const currentDesc = ref(
  skills.find(s => s.id === props.initialSkill)?.desc || skills[0].desc
)
const isTalking = ref(skills[0].id === 'beginner') // Just arbitrary animation logic

const handleSelect = (opt: any) => {
  emit('update:skill', opt.id)
  emit('next')
}

const handleHighlight = (opt: any) => {
  currentDesc.value = opt.desc
  isTalking.value = opt.id === 'beginner'
  emit('update:skill', opt.id)
}
</script>

<template>
  <div class="skill-select">
    <div class="select-label text-small text-silver tracking-[0.2em]">SELECT EXPERIENCE</div>
    
    <div class="skill-list">
      <CyberMenuList 
        :options="skills"
        :initial-option="initialSkill"
        @select="handleSelect"
        @highlight="handleHighlight"
        @back="emit('back')"
        :active="true"
      />
    </div>
    
    <!-- Coach preview -->
    <div class="mt-auto mb-2 w-full px-2">
      <DialogueBox 
        coach-id="trod"
        :emotion="isTalking ? 'talk' : 'idle'"
        :text="currentDesc"
      />
    </div>
  </div>
</template>

<style scoped>
.skill-select {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  padding-top: clamp(8px, 2vh, 20px);
  font-family: var(--font-ui);
  gap: clamp(8px, 2vh, 20px);
}

.select-label {
  margin-bottom: clamp(2px, 0.5vh, 6px);
}

.skill-list {
  display: flex;
  flex-direction: column;
  width: clamp(220px, 80vw, 450px);
}

</style>
