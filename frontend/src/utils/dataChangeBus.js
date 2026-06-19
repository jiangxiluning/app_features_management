const listeners = new Set()

export function onDataChangeRefresh(handler) {
  listeners.add(handler)
  return () => listeners.delete(handler)
}

export function triggerDataChangeRefresh(event) {
  listeners.forEach((handler) => {
    try {
      handler(event)
    } catch (e) {
      console.error('dataChange refresh handler failed', e)
    }
  })
}
