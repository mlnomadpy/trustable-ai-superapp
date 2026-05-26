import { ref, onUnmounted } from 'vue'

/**
 * Composable that creates a self-reconnecting EventSource.
 * On disconnect/error, it waits `retryMs` and retries up to `maxRetries` times.
 * Resets the retry counter on any successful message.
 *
 * @param url - The SSE endpoint URL
 * @param options - Configuration: event name, retry interval, max retries
 * @returns { data, isConnected, error, close }
 */
export function useReconnectingSSE(
  url: string,
  options: {
    eventName?: string
    retryMs?: number
    maxRetries?: number
    onMessage?: (data: string) => void
  } = {}
) {
  const { eventName, retryMs = 3000, maxRetries = 10, onMessage } = options

  const data = ref<string | null>(null)
  const isConnected = ref(false)
  const error = ref<string | null>(null)

  let es: EventSource | null = null
  let retryCount = 0
  let retryTimeout: number | null = null

  const connect = () => {
    es?.close()
    es = new EventSource(url)

    const handleMessage = (e: MessageEvent) => {
      retryCount = 0 // reset on success
      isConnected.value = true
      error.value = null
      data.value = e.data
      onMessage?.(e.data)
    }

    if (eventName) {
      es.addEventListener(eventName, handleMessage)
    } else {
      es.onmessage = handleMessage
    }

    es.onerror = () => {
      isConnected.value = false
      es?.close()
      es = null

      if (retryCount < maxRetries) {
        retryCount++
        error.value = `Disconnected — retry ${retryCount}/${maxRetries}`
        retryTimeout = window.setTimeout(connect, retryMs)
      } else {
        error.value = `Gave up after ${maxRetries} retries`
      }
    }
  }

  const close = () => {
    if (retryTimeout) clearTimeout(retryTimeout)
    retryTimeout = null
    es?.close()
    es = null
    isConnected.value = false
    retryCount = 0
  }

  onUnmounted(close)

  // Auto-connect
  connect()

  return { data, isConnected, error, close }
}
