# 双色球 AI 预测系统

## 项目概述

这是一个基于 AI 模型的双色球彩票预测系统，展示多个 AI 模型（GPT-5、Claude 4.5、Gemini 2.5、DeepSeek R1）对双色球开奖号码的预测，并提供历史预测准确率对比功能。

**核心特性**:
- 🤖 多 AI 模型预测展示
- 📊 历史开奖数据查询
- 🎯 预测命中率统计
- ⏰ 自动更新开奖数据（GitHub Actions）
- 🔮 下期开奖信息展示

**双色球规则**:
- 红球：从 01-33 中选择 6 个号码
- 蓝球：从 01-16 中选择 1 个号码
- 开奖时间：每周二、四、日 21:15

---

## 项目结构

```
Double-Color-Ball-AI/
├── index.html                    # 主页面
├── css/
│   └── style.css                 # 样式文件（支持深色/浅色主题）
├── js/
│   ├── app.js                    # 主应用逻辑
│   ├── components.js             # UI 组件
│   └── data-loader.js            # 数据加载模块
├── data/                         # 前端数据文件
│   ├── lottery_history.json      # 历史开奖数据 + 下期开奖信息
│   ├── ai_predictions.json       # 当前 AI 预测（未开奖期号）
│   └── predictions_history.json  # 历史预测对比数据（已开奖期号）
├── fetch_history/                # 数据爬取脚本
│   ├── fetch_lottery_history.py  # 爬虫脚本（自动同步到 data/）
│   ├── lottery_data.json         # 爬虫原始数据
│   └── lottery_data_backup_*.json # 自动备份文件（不提交到 Git）
├── .github/workflows/
│   └── update-lottery-data.yml   # GitHub Actions 自动更新配置
├── add_gpt5_prediction.py        # 辅助脚本：添加历史预测
├── start_server.sh / .bat        # 本地开发服务器启动脚本
├── vercel.json                   # Vercel 部署配置
├── DATA_UPDATE_GUIDE.md          # 数据更新指南
└── .gitignore                    # Git 忽略规则（排除备份文件）
```

---

## 核心数据文件

### 1. `data/lottery_history.json`
**用途**: 网页前端使用的历史开奖数据

**数据结构**:
```json
{
  "last_updated": "2025-10-22T20:39:53Z",
  "data": [
    {
      "period": "25121",
      "date": "2025-10-21",
      "red_balls": ["06", "08", "10", "25", "29", "30"],
      "blue_ball": "08"
    }
  ],
  "next_draw": {
    "next_period": "25122",
    "next_date": "2025-10-23",
    "next_date_display": "2025年10月23日",
    "weekday": "周四",
    "draw_time": "21:15"
  }
}
```

**更新方式**:
- 自动：GitHub Actions 每天 22:00 自动运行爬虫更新
- 手动：运行 `cd fetch_history && python3 fetch_lottery_history.py`

---

### 2. `data/ai_predictions.json`
**用途**: 当前 AI 模型对未开奖期号的预测

**数据结构**:
```json
{
  "prediction_date": "2025-10-23",
  "target_period": "25122",
  "models": [
    {
      "model_id": "SSB-Team-001",
      "model_name": "GPT-5",
      "predictions": [
        {
          "group_id": 1,
          "strategy": "热号追随者",
          "red_balls": ["02", "09", "17", "25", "31", "33"],
          "blue_ball": "02",
          "description": "策略描述..."
        }
        // 每个模型 5 组预测
      ]
    }
    // 4 个 AI 模型
  ]
}
```

**更新时机**: 当 `target_period` 开奖后，需要手动更新为下一期的预测

---

### 3. `data/predictions_history.json`
**用途**: 已开奖期号的历史预测和命中结果

**数据结构**:
```json
{
  "predictions_history": [
    {
      "prediction_date": "2025-10-21",
      "target_period": "25121",
      "actual_result": {
        "period": "25121",
        "date": "2025-10-21",
        "red_balls": ["06", "08", "10", "25", "29", "30"],
        "blue_ball": "08"
      },
      "models": [
        {
          "model_id": "SSB-Team-001",
          "model_name": "GPT-5",
          "predictions": [
            {
              "group_id": 1,
              "strategy": "热号追随者",
              "red_balls": ["02", "09", "17", "25", "31", "33"],
              "blue_ball": "02",
              "description": "...",
              "hit_result": {
                "red_hits": ["25"],
                "red_hit_count": 1,
                "blue_hit": false,
                "total_hits": 1
              }
            }
          ],
          "best_group": 2,
          "best_hit_count": 2
        }
      ]
    }
  ]
}
```

**更新方式**: 当期号开奖后，运行脚本计算命中结果并添加到历史

---

## 关键脚本

### `fetch_history/fetch_lottery_history.py`
**功能**:
1. 从 500.com 爬取最新双色球开奖数据
2. 与现有数据合并去重
3. 自动创建带时间戳的备份文件
4. **自动同步到 `../data/lottery_history.json`**（网页数据）
5. **自动计算下期开奖信息**（基于周二、四、日规律）

**运行方式**:
```bash
cd fetch_history
python3 fetch_lottery_history.py
```

**依赖**:
- `requests` - HTTP 请求
- `beautifulsoup4` - HTML 解析

---

### `add_gpt5_prediction.py`
**功能**: 将某期的 AI 预测添加到历史记录并计算命中结果

**使用场景**: 当某期开奖后，需要将预测数据从 `ai_predictions.json` 移到 `predictions_history.json`

**自动功能**:
- 计算红球命中数和蓝球命中情况
- 计算每个模型的最佳预测组
- 添加到历史记录顶部

---

## GitHub Actions 自动化

### 工作流文件
`.github/workflows/update-lottery-data.yml`

### 触发时机
- **定时**: 每天 UTC 14:00（北京时间 22:00）
- **手动**: GitHub Actions 页面点击 "Run workflow"

### 执行流程
1. 安装 Python 和依赖（requests, beautifulsoup4）
2. 运行 `fetch_lottery_history.py` 爬取数据
3. 检测 `data/` 目录是否有变更
4. 如有变更，自动提交并推送到仓库
5. Vercel 监听到仓库更新，自动重新部署

### 权限配置
确保仓库设置中启用了工作流写入权限：
- Settings > Actions > General > Workflow permissions
- 选择 **Read and write permissions**

---

## 前端架构

### 页面结构
- **顶部导航**: 标题、刷新按钮、主题切换
- **Tab 切换**:
  - AI 预测：下期开奖卡片 + 最新开奖结果 + 预测状态 + 多模型预测
  - 预测对比：历史预测命中率对比
  - 历史开奖：历史开奖记录列表

### 主要功能

#### 1. 下期开奖卡片
- 显示下期期号、日期、星期、开奖时间
- 智能检测是否有 AI 预测：
  - 🟢 已有AI预测
  - 🟡 暂无AI预测

#### 2. 预测状态
- 比较 `ai_predictions.json` 的 `target_period` 和最新开奖期号
- 显示两种状态：
  - 🔮 **未开奖**: target_period > 最新期号
  - ✅ **已开奖**: target_period ≤ 最新期号

#### 3. 模型选择器
- 下拉菜单切换不同 AI 模型
- 显示该模型的 5 组预测方案

#### 4. 历史预测对比
- 按期号分组显示所有模型的历史预测
- 高亮显示命中的号码
- 显示准确率徽章（优秀/良好/一般/较差）
- 标记每个模型的最佳预测组

### 主题切换
- 支持浅色/深色模式
- 使用 CSS 变量实现
- 状态保存在 localStorage

---

## 数据更新工作流

### 场景 1: 新期号开奖
1. **自动**: GitHub Actions 在 22:00 自动运行爬虫
2. **自动**: 更新 `lottery_history.json` 和 `next_draw` 信息
3. **自动**: 提交并部署到 Vercel
4. **手动**: 运行辅助脚本将旧预测移到历史：
   ```bash
   python3 add_gpt5_prediction.py
   ```
5. **手动**: 更新 `ai_predictions.json` 为新期号的预测

### 场景 2: 添加新模型预测
1. 编辑 `ai_predictions.json`
2. 添加新模型到 `models` 数组
3. 提交并推送到仓库
4. Vercel 自动重新部署

### 场景 3: 立即更新数据
1. 访问 GitHub 仓库
2. Actions > Update Lottery Data > Run workflow
3. 等待工作流完成
4. Vercel 自动部署

---

## 部署

### Vercel 部署
项目配置了 `vercel.json`，自动部署静态站点。

**配置说明**:
```json
{
  "headers": [
    {
      "source": "/data/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=0, must-revalidate"
        }
      ]
    }
  ]
}
```

**注意**: 不要同时使用 `routes` 和 `headers`，会导致部署失败。

### 本地开发
```bash
# macOS/Linux
./start_server.sh

# Windows
start_server.bat
```

访问 `http://localhost:8000`

---

## AI 预测策略

每个 AI 模型提供 5 种预测策略：

1. **热号追随者**: 选择最近 30 期高频号码
2. **冷号逆向者**: 选择最近 30 期低频号码，期待均值回归
3. **平衡策略师**: 满足奇偶比、大小比、和值、连号等多维平衡
4. **周期理论家**: 选择短期频率上穿长期频率的号码
5. **综合决策者**: 融合多种策略的综合方案

---

## 常见问题

### Q: GitHub Actions 运行失败怎么办？
**A**: 检查以下内容：
1. Actions 是否启用（Settings > Actions）
2. 工作流权限是否设置为读写（Settings > Actions > Workflow permissions）
3. Python 依赖是否正确安装
4. 查看 Actions 运行日志定位具体错误

### Q: 网页不显示最新数据？
**A**:
1. 清除浏览器缓存
2. 检查 `lottery_history.json` 是否已更新
3. 确认 Vercel 已重新部署（查看 Vercel Dashboard）
4. 验证 JSON 文件格式是否正确

### Q: 如何修改自动更新时间？
**A**: 编辑 `.github/workflows/update-lottery-data.yml` 中的 cron 表达式：
```yaml
schedule:
  - cron: '0 14 * * *'  # UTC 14:00 = 北京时间 22:00
```

### Q: 备份文件太多怎么办？
**A**: 备份文件已被 `.gitignore` 排除，不会提交到仓库。可以手动删除旧备份：
```bash
cd fetch_history
rm lottery_data_backup_*.json
```

---

## 技术栈

**前端**:
- HTML5
- CSS3 (CSS Variables, Grid, Flexbox)
- Vanilla JavaScript (ES6+)

**后端/数据**:
- Python 3
- requests + BeautifulSoup4（数据爬取）
- JSON（数据存储）

**自动化**:
- GitHub Actions
- Vercel（自动部署）

**工具**:
- Git（版本控制）
- Python HTTP Server（本地开发）

---

## 文件编码和格式

- 所有 JSON 文件：UTF-8，ensure_ascii=False，indent=2
- Python 文件：UTF-8，# -*- coding: utf-8 -*-
- HTML/CSS/JS：UTF-8

---

## Git 规则

### 提交信息格式
- `feat:` - 新功能
- `fix:` - 修复 bug
- `chore:` - 杂项（自动更新数据等）
- `docs:` - 文档更新
- `style:` - 代码格式调整

### .gitignore 关键规则
```
# 备份文件（本地保留，不提交）
*_backup_*.json
fetch_history/lottery_data_backup_*.json

# Python 缓存
__pycache__/
*.py[cod]

# 系统文件
.DS_Store
```

---

## 许可证

本项目仅供学习交流使用，不构成任何投资建议。彩票具有随机性，AI 预测仅为技术演示，不保证准确性。

---

## 维护者

如需帮助或报告问题，请参考：
- `DATA_UPDATE_GUIDE.md` - 数据更新详细指南
- GitHub Issues - 问题追踪
- 本文件 - 项目整体说明
