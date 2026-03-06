import re

# 模拟模板字符串处理
markdown_content = '''{{#videos}} 
# 教学视频德得的德 {{index + 1}} 
{{url}} 
{{/videos}} '''

# 使用正则表达式匹配videos模板部分
videos_match = re.search(r'\{\{#videos\}\}(.*?)\{\{/videos\}\}', markdown_content, re.DOTALL)
if videos_match:
    videos_section = videos_match.group(0)
    video_template = videos_match.group(1).lstrip()
    print(f"视频模板: {repr(video_template)}")

# 模拟视频数据
videos = ['http://www.baidu1.com', 'http://www.baidu2.com', 'http://www.baidu3.com']

# 生成内容
videos_content = ''
for i, video in enumerate(videos, 1):
    # 为每个video生成内容，使用用户定义的模板
    video_content = video_template.replace('{{index}}', str(i-1))
    video_content = video_content.replace('{{index + 1}}', str(i))
    video_content = video_content.replace('{{url}}', str(video))
    videos_content += video_content

print(f"生成的内容: {repr(videos_content)}")
print("\n实际输出:")
print(videos_content)

# 测试使用案例
print("\n=== 测试使用案例 ===")
use_cases_content = '''{{#use_cases}} 
## 案例 {{index + 1}} 
{{value}} 
{{/use_cases}} '''

use_cases_match = re.search(r'\{\{#use_cases\}\}(.*?)\{\{/use_cases\}\}', use_cases_content, re.DOTALL)
if use_cases_match:
    use_cases_section = use_cases_match.group(0)
    use_case_template = use_cases_match.group(1).lstrip()
    print(f"使用案例模板: {repr(use_case_template)}")

# 模拟使用案例数据
use_cases = ['使用案例1内容', '使用案例2内容', '使用案例3内容']

# 生成内容
use_cases_output = ''
for i, use_case in enumerate(use_cases, 1):
    # 为每个use_case生成内容，使用用户定义的模板
    case_content = use_case_template.replace('{{index}}', str(i-1))
    case_content = case_content.replace('{{index + 1}}', str(i))
    case_content = case_content.replace('{{value}}', str(use_case))
    use_cases_output += case_content

print(f"生成的内容: {repr(use_cases_output)}")
print("\n实际输出:")
print(use_cases_output)

# 测试支持设备
print("\n=== 测试支持设备 ===")
devices_content = '''{{#devices}} 
{{device_name}} 
{{/devices}} '''

devices_match = re.search(r'\{\{#devices\}\}(.*?)\{\{/devices\}\}', devices_content, re.DOTALL)
if devices_match:
    devices_section = devices_match.group(0)
    device_template = devices_match.group(1).lstrip()
    print(f"支持设备模板: {repr(device_template)}")

# 模拟设备数据
class Device:
    def __init__(self, release_name, release_year):
        self.release_name = release_name
        self.release_year = release_year

devices = [Device('matepad', 2023), Device('matepad', 2024), Device('ipad', 2022)]

# 按发布年份降序，发布名称字母序升序排列
devices.sort(key=lambda x: (-x.release_year, x.release_name))

# 生成内容
devices_output = ''
for device in devices:
    # 为每个device生成内容，使用用户定义的模板
    device_content = device_template.replace('{{device_name}}', f"{device.release_name} {device.release_year}")
    devices_output += device_content

print(f"生成的内容: {repr(devices_output)}")
print("\n实际输出:")
print(devices_output)
