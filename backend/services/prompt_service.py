# -*- coding: utf-8 -*-
"""
Prompt服务
处理prompt模板和占位符替换
"""


class PromptService:
    """Prompt服务类"""
    
    @staticmethod
    def render_prompt(template, context):
        """
        渲染prompt模板，替换占位符
        
        Args:
            template: 模板字符串，包含{{placeholder}}格式的占位符
            context: 字典，包含占位符对应的值
        
        Returns:
            渲染后的字符串
        """
        if not template:
            return ''
        
        result = template
        
        # 替换所有占位符
        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            if placeholder in result:
                result = result.replace(placeholder, str(value) if value is not None else '')
        
        return result
    
    @staticmethod
    def get_optimization_context(feature, app_node=None):
        """
        获取功能描述优化的上下文
        
        Args:
            feature: Feature对象，待优化的功能
            app_node: Feature对象，应用根节点（可选）
        
        Returns:
            包含上下文的字典
        """
        # 获取应用信息
        app_name = ''
        app_description = ''
        
        if app_node:
            app_name = app_node.name or ''
            app_description = app_node.description or ''
        elif feature and feature.parent_id:
            # 尝试从feature向上找到应用根节点
            current = feature
            while current and current.parent_id:
                current = current.parent
                if current and current.node_type == 'app':
                    app_name = current.name or ''
                    app_description = current.description or ''
                    break
        
        # 构建上下文
        context = {
            'app_name': app_name,
            'app_description': app_description,
            'feature_name': feature.name or '' if feature else '',
            'feature_description': feature.description or '' if feature else ''
        }
        
        return context
