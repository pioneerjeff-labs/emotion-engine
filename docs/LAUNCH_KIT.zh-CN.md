# Emotion Engine 发布素材

这个文档用于中文发布文案、PioneerJeff Labs 中文介绍和后续内容包装。

## 一句话介绍

给 LLM Agent 使用的情绪连续性状态层。

## 简短描述

一个轻量的 AI 智能体情绪连续性状态层：PAD 状态、信任、时间衰减和紧凑情绪日志。

## 中文发布文案

我发布了 PioneerJeff Labs 的第一个开源项目：Emotion Engine。

它不是一个聊天机器人，而是给大模型智能体使用的“情绪连续性状态层”：PAD 情绪状态、信任、时间衰减、紧凑情绪日志。

我的目标是把这种底层能力做成可检查、可迁移、可复用的开源模块，让它可以被更上层的应用项目接入。

目前仓库包含本地生命周期检查工具，以及 OpenClaw、Claude Skills 和 Hermes Agent 的初版集成。
同时也包含一个脚本化的并排网页演示，适合用于截图、短视频和公开介绍。演示内容基于经过匿名化和改编的过往 LLM 互动实验记录，但仍然是整理过的非实时演示。

Repo: https://github.com/pioneerjeff-labs/emotion-engine
在线演示：[https://pioneerjeff-labs.github.io/emotion-engine/demo/](https://pioneerjeff-labs.github.io/emotion-engine/demo/)

## 中文组织介绍

PioneerJeff Labs 关注面向创意 AI 应用的可复用基础设施层。每个项目都从一个具体创意或真实需求出发，把底层能力沉淀成小而清晰、可检查、可迁移的开源模块。

第一个项目 Emotion Engine 探索的是情绪连续性状态层：一个大模型智能体如何在不假装识别真实人类情绪的前提下，携带情绪状态、信任、边界和紧凑情绪记忆跨会话延续。

## 不要这样表述

- 不要说它能识别用户真实情绪。
- 不要把它包装成心理健康工具。
- 不要暗示 Python 脚本在真实集成里负责最终情绪判断。
- 不要把它包装成操控依恋或优化关系的工具。
