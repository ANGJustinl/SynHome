# SynHome 智能家居系统集成指南

本文档将帮助开发者理解 SynHome 智能家居系统架构，并指导如何将其集成到现有项目中。

## 目录

- [系统架构](#系统架构)
- [环境要求](#环境要求)
- [安装步骤](#安装步骤)
- [配置说明](#配置说明)
- [API 参考](#API-参考)
- [设备扩展指南](#设备扩展指南)
- [常见问题](#常见问题)

## 系统架构

SynHome 采用模块化设计，主要由以下几个核心组件构成：

1. **设备抽象层**：提供统一的设备接口和能力模型
   - `SmartDevice` 类：所有智能设备的基类，支持动态能力定义
   - `DeviceManager` 类：管理设备创建和命令路由

2. **通信层**：基于 FastAPI 的 RESTful 服务
   - 提供设备信息查询和命令下发接口
   - WebSocket 服务（可选）用于实时状态更新

3. **控制层**：基于 LLM 的自然语言处理
   - 使用智谱 AI 进行自然语言理解和意图识别
   - 指令解析和参数提取

4. **前端界面**：基于 Vue 和 Element Plus 的用户界面
   - 响应式设备状态显示
   - 自然语言命令输入

## 环境要求

- Python 3.8+
- Node.js 14+ (仅前端开发需要)
- 智谱 AI API 密钥 (用于自然语言处理)

## 安装步骤

1. 克隆仓库并安装依赖：

```bash
git clone https://github.com/yourusername/SynHome.git
cd SynHome
uv venv  # 或 python -m venv .venv
.venv\Scripts\activate
uv pip install -r requirements.txt  # 或 pip install -r requirements.txt
```

2. 配置智谱 AI API 密钥：

编辑 `config/demo.yaml` 文件，填入您的 API 密钥：

```yaml
zhipuai:
  enabled: true
  api_key: "your_api_key_here"
```

3. 启动服务：

```bash
cd apps/demo
python run.py
```

## 配置说明

SynHome 使用 YAML 配置文件来定义设备及其能力。配置文件位于 `config/demo.yaml`：

### 设备配置示例

```yaml
devices:
  - id: "device1"            # 设备唯一标识符
    name: "设备名称"          # 设备显示名称
    type: "设备类型"          # 设备类型，如 thermostat, light, rice_cooker 等
    capabilities:            # 设备的能力列表
      - power:               # 能力名称
          type: "switch"     # 能力类型：switch(开关)、number(数值)、enum(枚举)
          states: ["off", "on"]  # 开关类型的可选状态
      - brightness:          # 亮度能力示例
          type: "number"
          min: 0             # 最小值
          max: 100           # 最大值
          unit: "%"          # 单位（可选）
      - mode:                # 模式能力示例
          type: "enum"
          values: ["auto", "manual", "eco"]  # 枚举值列表
```

### 支持的能力类型

1. **开关类型 (switch)**：
   - 用于表示开/关状态
   - 必需参数: `states` - 可用状态列表，通常为 ["off", "on"]

2. **数值类型 (number)**：
   - 用于表示可调节的数值参数，如温度、亮度
   - 必需参数: `min`, `max` - 最小值和最大值
   - 可选参数: `unit` - 单位

3. **枚举类型 (enum)**：
   - 用于表示有限选项的参数，如模式、场景
   - 必需参数: `values` - 可选值列表

## API 参考

SynHome 提供以下 REST API 接口：

### 获取所有设备信息

```
GET /devices
```

响应示例：

```json
[
  {
    "id": "thermostat1",
    "name": "客厅空调",
    "type": "thermostat",
    "state": "ON",
    "capabilities": {
      "power": {
        "type": "switch",
        "current_value": "on",
        "states": ["off", "on"]
      },
      "temperature": {
        "type": "number",
        "current_value": 24,
        "min": 16,
        "max": 30,
        "unit": "°C"
      }
      // ...其他能力
    }
  }
  // ...其他设备
]
```

### 向特定设备发送命令

```
POST /devices/{device_id}/command
```

请求体：

```json
{
  "command": "把温度调高一点"
}
```

响应示例：

```json
{
  "success": true,
  "message": "Command executed successfully",
  "state": "ON",
  "capabilities": {
    // 更新后的设备能力状态
  }
}
```

### 全局命令（系统自动识别设备）

```
POST /command
```

请求体：

```json
{
  "command": "把客厅灯关掉"
}
```

响应示例：

```json
{
  "success": true,
  "message": "Command executed successfully on 客厅灯",
  "device_id": "light1"
}
```

## 设备扩展指南

要添加新类型的设备，只需在配置文件中按照上述格式定义设备及其能力。系统会自动创建相应的设备实例，并使用 LLM 处理相关命令。

### 创建新设备的步骤

1. 在 `config/demo.yaml` 文件中的 `devices` 列表中添加新设备定义：

```yaml
devices:
  # ...现有设备
  - id: "new_device1"
    name: "新设备名称" 
    type: "new_device_type"
    capabilities:
      # 定义设备能力
      - power:
          type: "switch"
          states: ["off", "on"]
      # 添加特定能力
      - custom_capability:
          type: "enum"
          values: ["value1", "value2", "value3"]
```

2. 重启应用程序。系统将自动加载新设备配置。

无需编写任何代码，SynHome 的 LLM 将自动理解如何处理新设备的命令。

## 常见问题

### 智谱 AI API 密钥如何获取？

访问 [智谱 AI 官网](https://open.bigmodel.cn/)，注册账号并创建应用以获取 API 密钥。

### 系统支持的最大设备数量是多少？

理论上没有硬性限制，但建议控制在 100 个以内，以确保系统响应速度。

### 如何调试 LLM 解析结果？

查看应用日志，所有 LLM 请求和响应都会记录在日志中。您可以通过修改 `config/demo.yaml` 中的日志级别获得更详细的信息：

```yaml
logging:
  level: DEBUG  # 改为 DEBUG 获取更详细日志
```

### 如何集成到现有项目？

1. 将 `libs` 目录复制到您的项目中
2. 引入 `DeviceManager` 和 `SmartDevice` 类
3. 创建配置加载逻辑和 API 接口，或直接使用 `apps/demo` 中的示例实现

### 如何扩展 LLM 能力？

可以修改 `libs/utils/llm.py` 中的 `ZhipuAIClient` 类，添加新的分析方法或更改系统提示。
