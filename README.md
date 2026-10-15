# CS2 每日道具

一个 AstrBot 插件：每天定时向已订阅的会话推送一条 CS2 实用道具教学（烟雾弹、闪光弹、燃烧弹、手雷），支持按地图学习和自定义发送时间。

## 功能

- 默认每天 12:00 推送一次，可在 WebUI 插件配置中修改时间点。
- 支持一天多次推送：在 `send_times` 中添加多个 `HH:MM` 时间点即可。
- 支持按时区推送，默认 `Asia/Shanghai`。
- 会话未选择地图时，每天随机推送一张地图的道具。
- 内置 Mirage、Dust2、Inferno、Nuke、Anubis、Ancient 六张地图的常用道具。
- 道具说明为社区常见投掷点的整理摘要，完整图文教程可点击消息中的来源链接查看。

## 使用

| 命令 | 作用 |
| --- | --- |
| `/subscribe` | 订阅当前会话的每日道具推送，默认随机地图 |
| `/unsubscribe` | 取消当前会话的每日推送 |
| `/map` | 查看当前地图和可选地图 |
| `/map 地图名` | 切换当前会话的推送地图，例如 `/map mirage` |
| `/map random` | 恢复为每日随机地图 |
| `/nade` | 立即学习一条道具 |

常用地图别名：`dust2`、`mirage`、`inferno`、`nuke`、`anubis`、`ancient`，也支持 `沙二`、`米垃圾`、`小镇` 等中文别名。

## 配置

安装后在 AstrBot WebUI 的插件配置页中调整：

- `send_times`：每日发送时间点列表，默认 `["12:00"]`。改成 `["12:00", "18:00"]` 即一天发送两次。
- `timezone`：定时任务使用的时区，默认 `Asia/Shanghai`。

## 数据来源

道具说明为作者整理的社区常见投掷点摘要，完整教学和点位图示请参考 [Tracker.gg CS2 Lineups](https://tracker.gg/cs2/lineups)。

## 安装

将本仓库克隆到 AstrBot 的 `data/plugins/` 目录：

```bash
cd data/plugins
git clone https://github.com/melancholy111/astrbot_plugin_cs2_Prop
```

也可以在 AstrBot WebUI 的插件市场安装，或上传本插件压缩包。
