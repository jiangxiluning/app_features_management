<template>
  <div class="register-container">
    <h2>用户注册</h2>
    <form @submit.prevent="register">
      <div class="form-group">
        <label for="username">用户名</label>
        <input type="text" id="username" v-model="form.username" required>
      </div>
      <div class="form-group">
        <label for="password">密码</label>
        <input type="password" id="password" v-model="form.password" required>
      </div>
      <div class="form-group">
        <label for="confirmPassword">确认密码</label>
        <input type="password" id="confirmPassword" v-model="form.confirmPassword" required>
      </div>
      <button type="submit" class="btn-submit">注册</button>
      <p class="login-link">已有账号？<router-link to="/login">去登录</router-link></p>
    </form>
    <div v-if="message" class="message" :class="messageType">{{ message }}</div>
  </div>
</template>

<script>
import { encryptPassword } from '../api'
import api from '../api'

export default {
  data() {
    return {
      form: {
        username: '',
        password: '',
        confirmPassword: ''
      },
      message: '',
      messageType: ''
    }
  },
  methods: {
    async register() {
      if (this.form.password !== this.form.confirmPassword) {
        this.message = '两次输入的密码不一致';
        this.messageType = 'error';
        return;
      }
      
      try {
        // 加密密码
        const encryptedPassword = await encryptPassword(this.form.password)
        const response = await api.post('/auth/register', {
          username: this.form.username,
          password: encryptedPassword.password,
          salt: encryptedPassword.salt,
          iv: encryptedPassword.iv
        });
        
        this.message = '注册成功，请登录';
        this.messageType = 'success';
        setTimeout(() => {
          this.$router.push('/login');
        }, 1500);
      } catch (error) {
        this.message = '网络错误，请稍后重试';
        this.messageType = 'error';
      }
    }
  }
}
</script>

<style scoped>
.register-container {
  max-width: 400px;
  margin: 100px auto;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  background-color: #fff;
}

h2 {
  text-align: center;
  margin-bottom: 20px;
  color: #333;
}

.form-group {
  margin-bottom: 20px;
}

label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #555;
}

input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
}

.btn-submit {
  width: 100%;
  padding: 12px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
  margin-top: 10px;
}

.btn-submit:hover {
  background-color: #45a049;
}

.login-link {
  text-align: center;
  margin-top: 20px;
  color: #666;
}

.login-link a {
  color: #4CAF50;
  text-decoration: none;
}

.login-link a:hover {
  text-decoration: underline;
}

.message {
  margin-top: 20px;
  padding: 10px;
  border-radius: 4px;
  text-align: center;
}

.success {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.error {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}
</style>