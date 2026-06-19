import { onMounted, onUnmounted, h } from 'vue'
import { ElNotification, ElButton, ElMessage } from 'element-plus'
import { triggerDataChangeRefresh } from '../utils/dataChangeBus'

const EVENT_LABELS = {
  features_changed: '功能数据已被他人更新',
  audit_submitted: '有新的待审核变更',
  audit_approved: '审核已通过，功能数据已更新',
  audit_rejected: '审核已拒绝，功能数据可能已变化',
  audit_withdrawn: '审核已撤回，功能数据可能已变化',
}

let source = null
let reconnectTimer = null

function getEventLabel(type) {
  return EVENT_LABELS[type] || '后台数据已发生变化'
}

function shouldIgnore(event) {
  const actor = event?.actor
  const self = localStorage.getItem('username')
  return actor && self && actor === self
}

function showRefreshNotice(event) {
  const label = getEventLabel(event.type)
  const actor = event.actor ? `（操作人：${event.actor}）` : ''

  ElNotification({
    title: '数据已更新',
    message: h('div', { style: 'line-height: 1.6' }, [
      h('p', { style: 'margin: 0 0 8px 0' }, `${label}${actor}`),
      h(
        ElButton,
        {
          type: 'primary',
          size: 'small',
          onClick: () => {
            triggerDataChangeRefresh(event)
            ElMessage.success('数据已刷新')
          },
        },
        () => '立即刷新'
      ),
    ]),
    type: 'warning',
    duration: 0,
    showClose: true,
    position: 'top-right',
  })
}

function connect() {
  const token = localStorage.getItem('token')
  if (!token) return

  if (source) {
    source.close()
    source = null
  }

  const url = `/api/events?token=${encodeURIComponent(token)}`
  source = new EventSource(url)

  source.addEventListener('data_change', (e) => {
    try {
      const payload = JSON.parse(e.data)
      if (shouldIgnore(payload)) return
      showRefreshNotice(payload)
    } catch (err) {
      console.error('SSE parse error', err)
    }
  })

  source.onerror = () => {
    if (source) {
      source.close()
      source = null
    }
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = setTimeout(connect, 5000)
  }
}

function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (source) {
    source.close()
    source = null
  }
}

export function useDataChangeSSE() {
  onMounted(() => connect())
  onUnmounted(() => disconnect())
}

export { connect as connectDataChangeSSE, disconnect as disconnectDataChangeSSE }
