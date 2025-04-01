# SynHome-同步之家 智能家居控制系统

基于大语言模型(LLM)的智能家居控制系统，使用自然语言控制和管理智能设备。

## 主要特点

- 完全动态配置 - 所有设备及其能力通过配置文件定义，无需硬编码
- 统一的设备抽象 - 使用SmartDevice类作为通用设备基类
- 灵活的能力定义 - 支持开关、数值和枚举三种类型的能力
- 自然语言控制 - 大语言模型(LLM)理解并处理各种自然语言指令
- 跨设备多操作支持 - 一个命令可以同时控制多个不同设备
- 设备状态智能控制 - 自动开启设备再设置参数

## 支持的设备类型

- 空调(Thermostat)
- 灯光(Light)
- 电饭煲(Rice Cooker)
- 智能插座(Socket)
- 扫地机器人(Vacuum)
- 智能窗帘(Curtain)

## 快速开始

请参考 [快速开始指南](docs/quick_start.md) 了解安装和基本使用方法。

## 文档

- [用户指南](docs/user_guide.md)
- [集成指南](docs/integration_guide.md)
- [设备配置指南](docs/device_configuration_guide.md)

## 许可证

[GPL-3.0 license](LICENSE)
