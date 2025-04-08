# SynHome 物理设备适配器指南

本文档详细介绍如何使用 SynHome 的物理设备适配器将真实的物理智能设备连接到系统中，实现统一的语音控制和管理。

## 目录

- [SynHome 物理设备适配器指南](#synhome-物理设备适配器指南)
  - [目录](#目录)
  - [概述](#概述)
  - [支持的适配器类型](#支持的适配器类型)
  - [WebSocket 适配器](#websocket-适配器)
    - [WebSocket 工作原理](#websocket-工作原理)
    - [WebSocket 配置参数](#websocket-配置参数)
    - [WebSocket 使用示例](#websocket-使用示例)
  - [MQTT 适配器](#mqtt-适配器)
    - [MQTT 工作原理](#mqtt-工作原理)
    - [MQTT 配置参数](#mqtt-配置参数)
    - [MQTT 使用示例](#mqtt-使用示例)
  - [适配器与设备关联](#适配器与设备关联)
  - [状态同步机制](#状态同步机制)
  - [故障排除](#故障排除)
    - [连接问题](#连接问题)
    - [命令执行失败](#命令执行失败)
    - [状态更新问题](#状态更新问题)
  - [错误处理和恢复机制](#错误处理和恢复机制)
    - [自动重连策略](#自动重连策略)
    - [手动重新初始化适配器](#手动重新初始化适配器)
  - [扩展开发](#扩展开发)

## 概述

SynHome 物理设备适配器是连接虚拟设备模型与实际物理设备的桥梁。通过适配器，您可以：

1. 将真实的智能家居设备接入系统
2. 使用统一的自然语言界面控制不同协议的设备
3. 实时监控设备状态变化
4. 自动同步物理设备状态到系统

所有适配器都遵循相同的接口规范，提供了一致的使用体验。

## 支持的适配器类型

SynHome 目前支持以下类型的设备适配器：

- **WebSocket 适配器**：通过 WebSocket 协议与支持此协议的设备或网关通信
- **MQTT 适配器**：通过 MQTT 协议与支持 MQTT 的设备或代理服务器通信

每个适配器类型都有其优势和适用场景：

| 适配器类型 | 适用场景 | 优势 | 局限性 |
|---------|--------|------|-------|
| WebSocket | 单个复杂设备、定制网关 | 全双工通信、低延迟 | 扩展性较低、连接数量有限 |
| MQTT | 大量简单设备、标准IoT平台 | 高扩展性、广泛支持、低带宽 | 额外依赖MQTT代理 |

## WebSocket 适配器

### WebSocket 工作原理

WebSocket 适配器通过建立持久的双向通信通道，实现系统与物理设备间的实时消息交换。工作流程如下：

1. 适配器连接到指定的 WebSocket 服务器端点
2. 对于需要身份验证的设备，发送认证信息
3. 发送设备发现请求，获取可用设备列表
4. 为发现的设备建立状态监听
5. 接收并转发命令到物理设备
6. 监听并处理设备状态变更事件

### WebSocket 配置参数

在 `config/demo.yaml` 文件中，WebSocket 适配器的配置如下：

```yaml
adapters:
  - id: "ws_adapter1"            # 适配器唯一标识符
    type: "websocket"            # 适配器类型
    config:
      url: "ws://192.168.1.100:8080/ws"  # WebSocket 服务器 URL
      use_ssl: false             # 是否使用 SSL/TLS
      verify_ssl: true           # 是否验证 SSL 证书
      timeout: 10                # 操作超时时间（秒）
      reconnect_delay: 5         # 重连延迟（秒）
      max_reconnect_attempts: 10 # 最大重连尝试次数
      ping_interval: 30          # 心跳间隔（秒）
      auto_reconnect: true       # 是否自动重连
      
      # 认证配置 (可选)
      auth:
        type: "token"            # 认证类型: none, token, basic, api_key
        token: "YOUR_AUTH_TOKEN" # 认证令牌 (用于 token 类型)
        # 或者使用基本认证
        # type: "basic"
        # username: "user"
        # password: "pass"
        
      # 消息格式配置
      message_format:
        command_template:        # 命令消息模板
          type: "command"
          device_id: "{device_id}"
          command: "{command}"
          params: "{params}"
        status_message_type: "status"  # 状态消息类型标识
      
      # 状态映射 (可选)
      status_map:
        # 将设备返回的状态字段映射到系统字段
        power_state:             # 设备中的字段名
          values:                # 值映射
            "1": "on"            # 设备值 -> 系统值 
            "0": "off"
        temperature_celsius: "temperature"  # 字段名映射
```

### WebSocket 使用示例

以下是一个配置与使用 WebSocket 适配器连接智能灯泡的示例：

```yaml
# 适配器配置
adapters:
  - id: "smart_bulb_ws"
    type: "websocket"
    config:
      url: "ws://192.168.1.200:81/smartlights"
      use_ssl: false
      auth:
        type: "api_key"
        api_key: "abcdef123456"
      message_format:
        command_template:
          cmd: "{command}"
          light_id: "{device_id}"
          parameters: "{params}"
        status_message_type: "light_update"
      status_map:
        pwr: "power"
        bri: "brightness"
        col: "color"

# 物理设备配置
physical_devices:
  - id: "living_room_bulb"
    name: "客厅智能灯泡"
    type: "light"
    adapter_id: "smart_bulb_ws"  # 关联的适配器ID
    device_id: "bulb001"         # 设备在适配器/物理系统中的ID
    capabilities:
      - power:
          type: "switch"
          states: ["off", "on"]
      - brightness:
          type: "number"
          min: 0
          max: 100
          unit: "%"
      - color:
          type: "enum"
          values: ["white", "warm", "cool", "red", "green", "blue"]
```

## MQTT 适配器

### MQTT 工作原理

MQTT 适配器利用发布/订阅模式与支持 MQTT 协议的设备或代理服务器进行通信。工作流程如下：

1. 适配器连接到指定的 MQTT 代理服务器
2. 订阅设备状态主题和发现响应主题
3. 发布设备发现请求
4. 处理发现响应，识别可用设备
5. 订阅每个设备的状态主题
6. 通过发布命令主题将控制命令发送给设备
7. 处理接收到的设备状态更新

### MQTT 配置参数

在 `config/demo.yaml` 文件中，MQTT 适配器的配置如下：

```yaml
adapters:
  - id: "mqtt_adapter1"          # 适配器唯一标识符
    type: "mqtt"                 # 适配器类型
    config:
      mqtt:
        host: "192.168.1.10"     # MQTT 代理服务器地址
        port: 1883               # MQTT 代理服务器端口
        username: "mqtt_user"    # MQTT 身份验证用户名 (可选)
        password: "mqtt_pass"    # MQTT 身份验证密码 (可选)
        use_ssl: false           # 是否使用 SSL/TLS
        client_id: "synhome_mqtt_client"  # 客户端 ID
        keepalive: 60            # Keepalive 间隔 (秒)
        
      # 主题配置
      topics:
        prefix: "home/"          # 主题前缀
        command: "devices/{device_id}/cmd"    # 命令主题模板
        status: "devices/{device_id}/state"   # 状态主题模板
        discovery: "discovery"   # 设备发现主题
        
      # 消息格式配置  
      message_format:
        command:                 # 命令格式
          cmd: "{command}"
          params: "{params}"
          
      # 状态映射 (可选)
      status_map:
        pwr: "power"             # 字段名映射
        tmp: "temperature"
        hum: "humidity"
        
      # 重连配置
      reconnect_delay: 5         # 重连延迟 (秒)
      max_reconnect_attempts: 10 # 最大重连尝试次数
      auto_reconnect: true       # 是否自动重连
```

### MQTT 使用示例

以下是一个配置与使用 MQTT 适配器连接智能温控器的示例：

```yaml
# 适配器配置
adapters:
  - id: "home_mqtt"
    type: "mqtt"
    config:
      mqtt:
        host: "192.168.1.5"
        port: 1883
        username: "homecontrol"
        password: "securepassword"
      topics:
        prefix: "smarthome/"
        command: "thermostat/{device_id}/set"
        status: "thermostat/{device_id}/status"
      message_format:
        command:
          action: "{command}"
          value: "{params}"
      status_map:
        current_temp: "temperature"
        target_temp: "target_temperature"
        mode: "mode"
        power: "power"

# 物理设备配置
physical_devices:
  - id: "bedroom_thermostat"
    name: "卧室温控器"
    type: "thermostat"
    adapter_id: "home_mqtt"      # 关联的适配器ID
    device_id: "therm_bedroom"   # 设备在MQTT系统中的ID
    capabilities:
      - power:
          type: "switch"
          states: ["off", "on"]
      - temperature:
          type: "number"
          min: 16
          max: 30
          unit: "°C"
      - mode:
          type: "enum"
          values: ["auto", "cool", "heat", "fan"]
```

## 适配器与设备关联

要将物理设备与系统中的虚拟设备模型关联，需要在配置文件中定义 `physical_devices` 部分：

```yaml
physical_devices:
  - id: "device_id"              # 系统中的设备ID
    name: "设备名称"              # 显示名称
    type: "设备类型"              # 设备类型
    adapter_id: "adapter_id"     # 关联的适配器ID
    device_id: "physical_id"     # 物理设备ID
    capabilities:                # 能力定义，与普通设备相同
      # 能力列表...
```

系统启动时，DeviceManager 会：
1. 创建并连接所有配置的适配器
2. 发现可用的物理设备
3. 将物理设备与配置中的虚拟设备关联
4. 设置状态同步机制

## 状态同步机制

设备适配器包含双向状态同步功能：

1. **系统到设备同步**：当用户通过自然语言命令改变设备状态时，系统会：
   - 转换命令为设备可理解的格式
   - 通过适配器发送到物理设备
   - 等待操作确认（如果支持）
   
2. **设备到系统同步**：当设备状态在物理世界中改变时，系统会：
   - 通过适配器接收状态更新
   - 应用状态映射转换
   - 更新系统中的虚拟设备状态
   - 更新用户界面显示

## 故障排除

### 连接问题

如果适配器无法连接到物理设备：

1. 检查网络连接是否正常
2. 确认IP地址、端口和URL是否正确
3. 验证认证信息是否正确
4. 查看防火墙是否阻止了连接
5. 检查日志中的详细错误信息

示例日志查找方法：
```bash
grep "adapter" logs/synhome.log
```

### 命令执行失败

如果命令无法正确执行：

1. 检查命令格式是否符合物理设备要求
2. 验证参数值是否在有效范围内
3. 确认设备状态是否允许执行该命令
4. 查看状态映射配置是否正确
5. 使用调试模式获取详细日志：

```yaml
# 在配置文件中启用调试日志
logging:
  level: DEBUG
```

### 状态更新问题

如果设备状态未正确同步：

1. 检查主题/URL配置是否正确
2. 验证状态映射配置
3. 确认物理设备是否正在发送状态更新
4. 查看状态消息格式是否符合预期

## 错误处理和恢复机制

### 自动重连策略

当物理设备连接中断时，适配器会尝试自动重新连接。重连策略由以下参数控制：

```yaml
adapters:
  - id: "ws_adapter"
    type: "websocket"
    config:
      # ...其他配置...
      reconnect_delay: 5         # 初始重连延迟（秒）
      max_reconnect_attempts: 10 # 最大重连尝试次数
      auto_reconnect: true       # 是否启用自动重连
```

系统使用指数退避策略进行重连，每次失败后延迟时间会增加，直到达到最大尝试次数。

### 手动重新初始化适配器

如果自动重连失败或需要手动重新初始化适配器，可以通过以下API调用：

## 扩展开发

SynHome 支持开发自定义适配器以连接更多类型的设备。要创建新的适配器类型：

1. 创建一个继承自 `DeviceAdapter` 基类的新类
2. 实现所有抽象方法
3. 在 `adapters/__init__.py` 中注册新的适配器类型

基本框架示例：

```python
from .base import DeviceAdapter

class MyCustomAdapter(DeviceAdapter):
    async def connect(self) -> bool:
        # 实现连接逻辑
        pass
        
    async def disconnect(self) -> None:
        # 实现断开连接逻辑
        pass
        
    async def discover_devices(self) -> List[Dict[str, Any]]:
        # 实现设备发现逻辑
        pass
        
    async def send_command(self, device_id: str, command: Dict[str, Any]) -> bool:
        # 实现命令发送逻辑
        pass

# 在 __init__.py 中注册
ADAPTER_TYPES["mycustom"] = MyCustomAdapter
```

详细的适配器开发指南请参考[开发文档](developer_guide.md).
