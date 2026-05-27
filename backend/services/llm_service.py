# -*- coding: utf-8 -*-
"""
大模型服务
封装OpenAI SDK调用逻辑
"""

from openai import OpenAI
import httpx


class LLMService:
    """大模型服务类"""
    
    def __init__(self, config):
        """
        初始化LLM服务
        
        Args:
            config: LLMConfig对象，包含配置信息
        """
        self.config = config
        self.client = self._create_client()
    
    def _create_client(self):
        """
        创建OpenAI客户端，支持代理配置
        
        Returns:
            OpenAI客户端实例
        """
        # 基础参数
        client_kwargs = {
            'api_key': self.config.api_key,
            'base_url': self.config.base_url,
            'timeout': 120.0,  # 设置超时时间为120秒
        }
        
        # 如果开启了不使用代理，则直接返回
        if getattr(self.config, 'no_proxy', False):
            return OpenAI(**client_kwargs)
        
        # 配置代理
        use_http_proxy = getattr(self.config, 'http_proxy', '')
        use_https_proxy = getattr(self.config, 'https_proxy', '')
        same_proxy = getattr(self.config, 'same_proxy', False)
        
        if same_proxy and use_http_proxy:
            # HTTP和HTTPS代理一致
            use_https_proxy = use_http_proxy
        
        if use_http_proxy or use_https_proxy:
            proxies = {}
            if use_http_proxy:
                proxies['http://'] = use_http_proxy
            if use_https_proxy:
                proxies['https://'] = use_https_proxy
            
            # 使用自定义httpx客户端，并设置超时
            http_client = httpx.Client(proxies=proxies, timeout=120.0)
            client_kwargs['http_client'] = http_client
        
        return OpenAI(**client_kwargs)
    
    def optimize_description(self, system_prompt, user_prompt):
        """
        使用大模型优化功能描述
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词（包含待优化的内容）
        
        Returns:
            优化后的描述文本
        """
        extra_body = {}
        if self.config.enable_search:
            extra_body["enable_search"] = True
        
        completion = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            extra_body=extra_body
        )
        
        return completion.choices[0].message.content
    
    def test_connection(self):
        """
        测试大模型连接
        
        Returns:
            (success: bool, message: str)
        """
        try:
            print(f"DEBUG - LLM测试连接 - 配置信息:")
            print(f"  base_url: {self.config.base_url}")
            print(f"  model_name: {self.config.model_name}")
            print(f"  no_proxy: {getattr(self.config, 'no_proxy', False)}")
            print(f"  same_proxy: {getattr(self.config, 'same_proxy', False)}")
            print(f"  http_proxy: {getattr(self.config, 'http_proxy', '')}")
            print(f"  https_proxy: {getattr(self.config, 'https_proxy', '')}")
            
            completion = self.client.chat.completions.create(
                model=self.config.model_name,
                messages=[
                    {'role': 'user', 'content': 'Hello'}
                ],
                max_tokens=10
            )
            print(f"DEBUG - LLM测试连接成功: {completion}")
            return True, "连接成功"
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"DEBUG - LLM测试连接失败: {str(e)}")
            print(f"DEBUG - 详细错误堆栈:\n{error_trace}")
            return False, str(e)
