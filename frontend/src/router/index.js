import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue')
  },
  {
    path: '/',
    name: 'home',
    component: () => import('../views/Home.vue'),
    redirect: '/features',
    children: [
      {
        path: 'features',
        name: 'features',
        component: () => import('../views/Features.vue')
      },
      {
        path: 'statistics',
        name: 'statistics',
        component: () => import('../views/Statistics.vue')
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('../views/Users.vue')
      },
      {
        path: 'audit',
        name: 'audit',
        component: () => import('../views/Audit.vue'),
        redirect: '/audit/approval',
        children: [
          {
            path: 'approval',
            name: 'auditApproval',
            component: () => import('../views/AuditApproval.vue')
          },
          {
            path: 'log',
            name: 'auditLog',
            component: () => import('../views/AuditLog.vue')
          }
        ]
      },
      {
        path: 'backup',
        name: 'backup',
        component: () => import('../views/Backup.vue')
      },
      {
        path: 'devices',
        name: 'devices',
        component: () => import('../views/Devices.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'login' && !token) {
    next({ name: 'login' })
  } else {
    next()
  }
})

export default router
