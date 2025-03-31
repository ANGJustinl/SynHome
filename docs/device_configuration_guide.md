# SynHome 设备配置指南

本指南详细介绍如何通过配置文件为SynHome系统添加和定义新的智能设备，无需编写代码。

## 目录

- [设备配置基础](#设备配置基础)
- [配置文件结构](#配置文件结构)
- [能力类型详解](#能力类型详解)
- [设备类型示例](#设备类型示例)
- [高级配置选项](#高级配置选项)
- [配置验证与测试](#配置验证与测试)
- [故障排除](#故障排除)

## 设备配置基础

SynHome系统采用基于配置的方法来定义设备，而不是硬编码设备类型。这种方法允许您：

- 无需编程即可添加新设备
- 动态定义设备的能力和参数
- 灵活调整设备配置以满足特定需求

所有设备配置都存储在`config/demo.yaml`文件中，使用YAML格式。

## 配置文件结构

设备配置采用以下基本结构：

```yaml
devices:
  - id: "unique_device_id"    # 唯一设备标识符
    name: "设备显示名称"       # 用户界面中显示的名称
    type: "device_type"       # 设备类型标识符
    capabilities:             # 设备能力列表
      - capability_name:      # 能力名称
          type: "capability_type"  # 能力类型
          # 特定于能力类型的其他参数...
```

每个设备必须具有唯一的`id`，用于系统内部识别，以及用户友好的`name`和标识设备种类的`type`。

## 能力类型详解

SynHome支持三种基本的能力类型：

### 1. 开关能力 (switch)

用于表示具有两种状态的功能，通常是开启/关闭。

```yaml
- power:
    type: "switch"
    states: ["off", "on"]     # 可选状态列表
```

参数：
- `states`: 状态列表，通常是 ["off", "on"]

示例用途：电源开关、功能启用/禁用控制

### 2. 数值能力 (number)

用于表示可调节的数值参数。

```yaml
- temperature:
    type: "number"
    min: 16                  # 最小值
    max: 30                  # 最大值
    unit: "°C"               # 单位（可选）
```

参数：
- `min`: 允许的最小值
- `max`: 允许的最大值
- `unit`: 显示单位（可选）

示例用途：温度设置、亮度调节、音量控制

### 3. 枚举能力 (enum)

用于从预定义选项列表中选择一个值。

```yaml
- mode:
    type: "enum"
    values: ["auto", "cool", "heat", "fan"]  # 可选值列表
```

参数：
- `values`: 可选值列表

示例用途：模式选择、场景设置、预设程序

## 设备类型示例

下面是几种常见设备类型的完整配置示例：

### 智能灯泡

```yaml
- id: "living_room_light"
  name: "客厅灯"
  type: "light"
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
        values: ["white", "warm", "natural", "cool"]
```

### 智能插座

```yaml
- id: "kitchen_socket"
  name: "厨房插座"
  type: "socket"
  capabilities:
    - power:
        type: "switch"
        states: ["off", "on"]
    - timer:
        type: "number"
        min: 0
        max: 86400  # 24小时（秒）
        unit: "秒"
    - mode:
        type: "enum"
        values: ["normal", "energy_saving", "protection"]
```

### 扫地机器人

```yaml
- id: "robot_vacuum"
  name: "扫地机器人"
  type: "vacuum"
  capabilities:
    - power:
        type: "switch"
        states: ["off", "on"]
    - mode:
        type: "enum"
        values: ["auto", "spot", "edge", "zigzag"]
    - suction:
        type: "enum"
        values: ["low", "medium", "high", "turbo"]
    - battery:
        type: "number"
        min: 0
        max: 100
        unit: "%"
```

### 智能窗帘

```yaml
- id: "bedroom_curtain"
  name: "卧室窗帘"
  type: "curtain"
  capabilities:
    - power:
        type: "switch"
        states: ["off", "on"]
    - position:
        type: "number"
        min: 0
        max: 100
        unit: "%"
    - mode:
        type: "enum"
        values: ["manual", "auto", "schedule"]
```

## 高级配置选项

### 设置初始值

您可以为能力设置初始值：

```yaml
- brightness:
    type: "number"
    min: 0
    max: 100
    unit: "%"
    current_value: 80  # 初始亮度设置为80%
```

### 设备分组

如果需要创建多个相似设备，可以使用类似模板的方法：

```yaml
# 客厅灯具组
- id: "living_room_light_1"
  name: "客厅主灯"
  type: "light"
  capabilities:
    # 与其他灯相同的能力...
    
- id: "living_room_light_2"
  name: "客厅辅灯"
  type: "light"
  capabilities:
    # 与其他灯相同的能力...
```

## 配置验证与测试

添加新设备后，请按照以下步骤验证配置：

1. **语法检查**: 确保YAML格式正确，没有缩进错误
   ```bash
   python -c "import yaml; yaml.safe_load(open('config/demo.yaml'))"
   ```

2. **重启系统**: 配置更改后需要重启SynHome系统
   ```bash
   cd apps/demo
   python run.py
   ```

3. **界面验证**: 打开web界面，检查新设备是否正确显示
   - 访问: http://localhost:8000/static/index.html
   - 验证设备名称、图标和能力是否正确显示

4. **功能测试**: 使用自然语言命令测试设备功能
   - 例如: "打开客厅灯" 或 "把窗帘拉到一半"
   - 验证系统是否正确理解和执行命令

## 故障排除

### 常见问题

1. **设备未显示**
   - 检查配置文件中设备ID是否唯一
   - 验证YAML语法是否正确

2. **能力无法控制**
   - 确保能力名称在系统中是已知的
   - 检查值范围是否符合预期

3. **LLM无法理解命令**
   - 设备类型名称使用常见、直观的词语
   - 能力名称使用标准术语，如"brightness"而非"light_level"

### 配置调试技巧

启用详细日志以帮助调试配置问题：

```yaml
# 在config/demo.yaml中
logging:
  level: DEBUG
```

### 设备类型指南

为确保LLM更好地理解您的设备，建议使用以下常见设备类型名称：

- `thermostat`: 空调、温控设备
- `light`: 灯具、照明设备
- `speaker`: 音响、扬声器
- `curtain`: 窗帘、百叶窗
- `socket`: 插座、电源插口
- `tv`: 电视、显示设备
- `vacuum`: 吸尘器、扫地机器人
- `fan`: 风扇、空气循环设备
- `humidifier`: 加湿器
- `air_purifier`: 空气净化器

---

本指南旨在帮助您充分利用SynHome的配置驱动设计。通过适当的设备配置，您可以创建丰富多样的智能家居体验，而无需编写任何代码。
