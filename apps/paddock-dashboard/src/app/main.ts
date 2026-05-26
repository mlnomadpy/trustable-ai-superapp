import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { router } from './router'
import App from './App.vue'

// Import global styles (Tailwind v4)
import './styles/global.css'
import './styles/buttons.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

app.config.errorHandler = (err, _instance, info) => {
  console.error(`[Pitwall] Unhandled error in ${info}:`, err)
}

app.mount('#app')
