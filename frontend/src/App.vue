<template>
  <div class="app">
    <router-view />
  </div>
</template>

<script setup>
// 简化App.vue，完全依赖路由守卫处理登录状态
</script>

<style scoped>
.app {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}
</style>
