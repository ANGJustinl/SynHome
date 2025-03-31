# SynHome 快速开始指南

本指南将帮助您在5分钟内完成 SynHome 智能家居系统的设置和初步使用。

## 1. 系统要求

- Windows 10/11 或 Linux/macOS
- Python 3.8 或更高版本
- 智谱 AI API 密钥（用于自然语言处理）

## 2. 安装步骤

### 安装 Python 依赖

```bash
# 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# 或 source .venv/bin/activate  # Linux/macOS

# 安装依赖
pip install -r requirements.txt
```

### 配置智谱 AI API

1. 编辑 `config/demo.yaml` 文件
2. 在 `zhipuai` 部分填入您的 API 密钥：
   ```yaml
   zhipuai:
     enabled: true
     api_key: "您的API密钥"
   ```

## 3. 启动系统

```bash
cd apps/demo
python run.py  # 或 .\start.bat (Windows)
```

系统将自动打开浏览器访问控制界面。如果没有自动打开，请访问：
http://localhost:8000/static/index.html

## 4. 试用系统

打开控制界面后，您可以看到当前连接的所有设备。尝试发送以下命令：

- "打开客厅灯"
- "把温度设置为24度"
- "开始煮饭"

## 5. 添加新设备

要添加新设备，编辑 `config/demo.yaml` 文件，在 `devices` 部分添加新设备配置：

```yaml
devices:
  # 现有设备...
  
  - id: "new_device1"
    name: "新设备名称"
    type: "设备类型"
    capabilities:
      - power:
          type: "switch"
          states: ["off", "on"]
      # 添加其他能力...
```

保存文件并重启系统后，新设备将自动显示在界面上。

## 6. 下一步

- 查看 [用户指南](user_guide.md) 了解更多使用方法
- 查看 [集成指南](integration_guide.md) 了解如何将系统集成到其他项目
- 体验不同类型的自然语言命令，探索系统的智能理解能力

## 7. 故障排除

如果遇到问题：

- 检查 API 密钥是否正确
- 验证网络连接是否正常
- 检查控制台日志获取错误信息
- 重启应用程序

如需更多帮助，请参考完整的 [用户指南](user_guide.md) 或联系系统管理员。
