import { defineStore } from 'pinia'
import { markRaw } from 'vue'

// Map known sheet IDs to their subdirectories in /sprites/
const SHEET_DIRS: Record<string, string> = {
  trod: 'coaches', bentley: 'coaches', drill: 'coaches', calm: 'coaches', buddy: 'coaches',
  avatar_a: 'coaches', avatar_b: 'coaches', avatar_c: 'coaches', avatar_d: 'coaches',
  avatars: 'drivers',
  frames: 'ui', medals: 'ui',
  'sonoma-map': 'tracks', 'sonoma-corners': 'tracks', 'sonoma-world-pin': 'tracks', 'sonoma-bg': 'tracks',
  wipes: 'effects', confetti: 'effects', dust: 'effects'
}

interface SpriteData {
  frames: Record<string, {
    frame: { x: number, y: number, w: number, h: number },
    spriteSourceSize: { x: number, y: number, w: number, h: number },
    sourceSize: { w: number, h: number }
  }>
  animations: Record<string, {
    frames: string[],
    fps: number,
    loop: boolean
  }>
  meta: { image: string }
}

export const useSpriteStore = defineStore('sprites', {
  state: () => ({
    loadedSheets: markRaw(new Set<string>()),
    sheetData: {} as Record<string, SpriteData>,
    injectedStyles: null as HTMLStyleElement | null,
    _injectedKeyframes: markRaw(new Set<string>())
  }),
  actions: {
    async loadSheet(sheet: string) {
      if (this.loadedSheets.has(sheet)) return
      
      const dir = SHEET_DIRS[sheet] || 'ui'
      
      // Coaches use algorithmic grid extraction, no JSON needed
      if (dir === 'coaches') {
        this.loadedSheets.add(sheet)
        return
      }
      
      try {
        const response = await fetch(`/sprites/${dir}/${sheet}.json`)
        if (!response.ok) throw new Error(`Failed to load ${sheet}.json`)
        
        const data: SpriteData = await response.json()
        this.sheetData[sheet] = data
        
        this.injectKeyframes(sheet, data)
        this.loadedSheets.add(sheet)
      } catch (e) {
        console.warn(`[spriteStore] Could not load sheet '${sheet}':`, e)
      }
    },
    
    injectKeyframes(sheet: string, data: SpriteData) {
      if (!this.injectedStyles) {
        this.injectedStyles = document.createElement('style')
        this.injectedStyles.id = 'pitwall-sprite-keyframes'
        document.head.appendChild(this.injectedStyles)
      }
      
      let cssText = ''
      
      for (const [animId, animObj] of Object.entries(data.animations || {})) {
        const step = 100 / animObj.frames.length
        cssText += `@keyframes sprite-${sheet}-${animId} {\n`
        
        for (let i = 0; i < animObj.frames.length; i++) {
          const frameId = animObj.frames[i]
          const fData = data.frames[frameId]
          if (!fData) continue
          
          const startPct = (i * step).toFixed(2)
          const endPct = ((i + 1) * step - 0.01).toFixed(2)
          
          // Generate discrete keyframe steps
          cssText += `  ${startPct}%, ${endPct}% { `
          cssText += `background-position: -${fData.frame.x}px -${fData.frame.y}px; `
          cssText += `width: ${fData.frame.w}px; `
          cssText += `height: ${fData.frame.h}px; `
          cssText += `}\n`
        }
        cssText += `}\n`
      }
      
      this.injectedStyles.appendChild(document.createTextNode(cssText))
    },
    
    cssFor(sheet: string, animation: string, options: { scale: number, paused: boolean }) {
      const dir = SHEET_DIRS[sheet] || 'ui'
      
      if (dir === 'coaches') {
        // Algorithmic extraction for 10x10 unified master coach sheets
        const animMap: Record<string, string> = { 'relaxed': 'idle' }
        let validAnim = animMap[animation] || animation
        
        const rowMap: Record<string, number> = {
          'idle': 0,
          'talk': 1,
          'victory': 2,
          'disappointed': 3,
          'concerned': 4,
          'intense': 5
        }
        
        if (!(validAnim in rowMap)) validAnim = 'idle'
        const rowIdx = rowMap[validAnim]
        
        // Define fps per action to give them unique feel
        const fpsMap: Record<string, number> = {
          'idle': 8, 'talk': 12, 'victory': 10, 'disappointed': 8, 'concerned': 10, 'intense': 12
        }
        const fps = fpsMap[validAnim] || 10
        const durationMs = (10 / fps) * 1000
        
        if (!this.injectedStyles) {
          this.injectedStyles = document.createElement('style')
          this.injectedStyles.id = 'pitwall-sprite-keyframes'
          document.head.appendChild(this.injectedStyles)
        }
        
        const animKeyName = `pitwall-master-row-${rowIdx}`
        const yPos = ((rowIdx / 9) * 100).toFixed(6) + '%'
        
        // Use insertRule() for O(1) injection instead of innerHTML += which re-parses entire stylesheet
        if (!this._injectedKeyframes.has(animKeyName)) {
          let kf = `@keyframes ${animKeyName} {\n`
          for (let i = 0; i < 10; i++) {
            const start = i * 10
            const end = start + 9.99
            const xPos = ((i / 9) * 100).toFixed(6) + '%'
            kf += `  ${start}%, ${end}% { background-position: ${xPos} ${yPos}; }\n`
          }
          kf += `}\n`
          try {
            this.injectedStyles.sheet?.insertRule(kf, this.injectedStyles.sheet.cssRules.length)
          } catch (_) {
            // Fallback for environments where insertRule fails (e.g., some test runners)
            this.injectedStyles.textContent += kf
          }
          this._injectedKeyframes.add(animKeyName)
        }
        
        const isAvatar = sheet.startsWith('avatar_')
        const basePath = isAvatar ? '/sprites/drivers' : '/sprites/coaches'
        
        return {
          backgroundImage: `url(${basePath}/${sheet}.png)`,
          backgroundSize: '1000% 1000%',
          backgroundRepeat: 'no-repeat',
          imageRendering: 'auto' as const,
          animationName: animKeyName,
          animationDuration: `${durationMs}ms`,
          animationTimingFunction: 'linear',
          animationIterationCount: 'infinite',
          animationPlayState: options.paused ? 'paused' : 'running',
          transform: `scale(${options.scale})`,
          transformOrigin: 'top left',
          display: 'inline-block',
          width: '100%',
          height: '100%'
        }
      }
      
      if (!this.loadedSheets.has(sheet)) {
        this.loadSheet(sheet)
        return { display: 'none' } // Hide until loaded
      }
      
      const data = this.sheetData[sheet]
      const animDef = data?.animations?.[animation]
      
      if (!animDef) {
        // Fallback if animation missing for legacy json sheets
        return {
          backgroundImage: `url(/sprites/${dir}/${sheet}.png)`,
          backgroundSize: 'contain',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          width: '64px',
          height: '96px',
          imageRendering: 'auto' as const,
          display: 'inline-block'
        }
      }
      
      const durationMs = (animDef.frames.length / animDef.fps) * 1000
      
      return {
        backgroundImage: `url(/sprites/${dir}/${sheet}.png)`,
        animationName: `sprite-${sheet}-${animation}`,
        animationDuration: `${durationMs}ms`,
        animationTimingFunction: 'linear', // Discrete steps are handled inside the keyframes
        animationIterationCount: animDef.loop ? 'infinite' : '1',
        animationPlayState: options.paused ? 'paused' : 'running',
        transform: `scale(${options.scale})`,
        transformOrigin: 'top left', // Ensure scaling anchors properly
        display: 'inline-block'
      }
    }
  }
})
