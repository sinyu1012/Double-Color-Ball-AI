# 数据更新指南

本文档说明如何更新双色球数据系统的各类数据。

## 📊 数据文件说明

### 1. 历史开奖数据
- **位置**: `data/lottery_history.json`
- **格式**: 包含 `last_updated`、`data` 数组和 `next_draw` 对象
- **用途**: 网页显示历史开奖记录和下期开奖信息

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

### 2. 当前 AI 预测数据
- **位置**: `data/ai_predictions.json`
- **格式**: 包含 `prediction_date`, `target_period`, `models` 数组
- **用途**: 网页显示最新AI预测（未开奖期号）

### 3. 历史预测对比数据
- **位置**: `data/predictions_history.json`
- **格式**: 包含 `predictions_history` 数组，每个记录包含预测和实际结果
- **用途**: 网页显示历史预测准确率对比

---

## 🔄 更新流程

### 步骤 1: 更新历史开奖数据

#### 方法一：GitHub Actions 自动更新（推荐）⭐

项目已配置 GitHub Actions 自动化工作流，**无需手动操作**：

- ⏰ **自动触发**: 每天北京时间 22:00 自动运行
- 🤖 **自动抓取**: 从 500 彩票网获取最新数据
- 📦 **自动提交**: 检测到新数据时自动提交到仓库
- 🚀 **自动部署**: Vercel 监听仓库变更自动重新部署

**手动触发**（如需立即更新）：
1. 访问 GitHub 仓库
2. 进入 **Actions** 标签页
3. 选择 **Update Lottery Data** 工作流
4. 点击 **Run workflow** 按钮

**查看运行日志**：
- Actions 页面可查看每次自动更新的详细日志
- 成功时显示 "✅ Lottery data updated successfully"
- 无新数据时显示 "ℹ️ No new lottery data available"

#### 方法二：本地使用爬虫脚本

```bash
cd fetch_history
python3 fetch_lottery_history.py
```

**脚本会自动**:
- ✅ 从 500 彩票网爬取最新数据
- ✅ 与现有数据合并去重
- ✅ 创建备份文件（带时间戳）
- ✅ 保存到 `lottery_data.json`
- ✅ **自动同步到** `../data/lottery_history.json`
- ✅ **自动计算下期开奖信息**（期号、日期、星期）

#### 方法三：手动更新

1. 编辑 `data/lottery_history.json`
2. 更新 `last_updated` 时间戳
3. 在 `data` 数组开头添加新期号

```json
{
  "last_updated": "2025-10-22T10:00:00Z",
  "data": [
    {
      "period": "25122",
      "date": "2025-10-22",
      "red_balls": ["01", "05", "12", "20", "28", "31"],
      "blue_ball": "09"
    },
    // ... 其他历史数据
  ]
}
```

---

### 步骤 2: 处理已开奖的预测

当 `ai_predictions.json` 中的 `target_period` 已经开奖后：

#### 2.1 将预测移至历史记录

1. 打开 `data/predictions_history.json`
2. 在 `predictions_history` 数组开头添加新记录：

```json
{
  "prediction_date": "2025-10-22",
  "target_period": "25122",
  "actual_result": {
    "period": "25122",
    "date": "2025-10-22",
    "red_balls": ["01", "05", "12", "20", "28", "31"],
    "blue_ball": "09"
  },
  "models": [
    // 复制 ai_predictions.json 中的 models 数组
  ]
}
```

#### 2.2 计算命中结果

为每个预测组添加 `hit_result`:

```json
{
  "group_id": 1,
  "strategy": "热号追随者",
  "red_balls": ["02", "05", "17", "25", "31", "33"],
  "blue_ball": "02",
  "description": "...",
  "hit_result": {
    "red_hits": ["05", "31"],        // 命中的红球
    "red_hit_count": 2,              // 红球命中数
    "blue_hit": false,               // 蓝球是否命中
    "total_hits": 2                  // 总命中数
  }
}
```

#### 2.3 标记最佳预测组

为每个模型添加 `best_group` 和 `best_hit_count`:

```json
{
  "model_id": "SSB-Team-001",
  "model_name": "GPT-5",
  "predictions": [ /* ... */ ],
  "best_group": 2,           // 命中最多的组号
  "best_hit_count": 3        // 最高命中数
}
```

---

### 步骤 3: 更新当前预测（未开奖期号）

编辑 `data/ai_predictions.json`:

1. 更新 `prediction_date` 为今天日期
2. 更新 `target_period` 为下一个未开奖期号
3. 更新 `models` 数组中的预测数据

```json
{
  "prediction_date": "2025-10-23",
  "target_period": "25123",
  "models": [
    {
      "model_id": "SSB-Team-001",
      "model_name": "GPT-5",
      "predictions": [
        {
          "group_id": 1,
          "strategy": "热号追随者",
          "red_balls": ["03", "08", "15", "22", "29", "32"],
          "blue_ball": "05",
          "description": "..."
        }
        // ... 其他4组预测
      ]
    }
    // ... 其他模型
  ]
}
```

---

## 🤖 自动化脚本（可选）

创建 `update_predictions.py` 脚本来自动化步骤 2：

```python
import json
from datetime import datetime

def move_to_history():
    # 读取当前预测
    with open('data/ai_predictions.json', 'r') as f:
        current = json.load(f)

    # 读取历史数据
    with open('data/lottery_history.json', 'r') as f:
        history = json.load(f)

    # 找到对应期号的开奖结果
    target_period = current['target_period']
    actual = next((r for r in history['data'] if r['period'] == target_period), None)

    if actual:
        # 计算命中结果
        for model in current['models']:
            for pred in model['predictions']:
                red_hits = [b for b in pred['red_balls'] if b in actual['red_balls']]
                blue_hit = pred['blue_ball'] == actual['blue_ball']
                pred['hit_result'] = {
                    'red_hits': red_hits,
                    'red_hit_count': len(red_hits),
                    'blue_hit': blue_hit,
                    'total_hits': len(red_hits) + (1 if blue_hit else 0)
                }

            # 找出最佳组
            best = max(model['predictions'], key=lambda p: p['hit_result']['total_hits'])
            model['best_group'] = best['group_id']
            model['best_hit_count'] = best['hit_result']['total_hits']

        # 添加到历史
        with open('data/predictions_history.json', 'r') as f:
            pred_history = json.load(f)

        pred_history['predictions_history'].insert(0, {
            'prediction_date': current['prediction_date'],
            'target_period': target_period,
            'actual_result': actual,
            'models': current['models']
        })

        with open('data/predictions_history.json', 'w') as f:
            json.dump(pred_history, f, ensure_ascii=False, indent=2)

        print(f"✓ 已将 {target_period} 期预测移至历史记录")

if __name__ == '__main__':
    move_to_history()
```

---

## 📋 检查清单

每次更新数据后，请检查：

- [ ] `lottery_history.json` 包含最新开奖数据
- [ ] `ai_predictions.json` 的 `target_period` 是未开奖期号
- [ ] 如果有新开奖期号，已将旧预测移至 `predictions_history.json`
- [ ] 历史预测中已计算 `hit_result`
- [ ] 每个模型标记了 `best_group`
- [ ] 更新了 `last_updated` 时间戳

---

## 🚀 部署到 Vercel

更新数据后部署：

```bash
# 提交更新
git add data/
git commit -m "Update lottery data $(date +%Y-%m-%d)"
git push origin main

# Vercel 会自动重新部署
```

或手动部署：

```bash
vercel --prod
```

---

## 💡 提示

1. **自动化优先**: GitHub Actions 已配置自动更新，推荐直接使用
2. **手动触发**: 需要立即更新时，可在 GitHub Actions 页面手动运行工作流
3. **备份重要**: 爬虫脚本会自动创建备份，手动更新前也建议备份
4. **数据验证**: 更新后在本地测试（`./start_server.sh`）
5. **期号格式**: 确保期号格式一致（如 "25122"）
6. **日期格式**: 使用 ISO 8601 格式（`2025-10-22T10:00:00Z`）
7. **JSON 格式**: 使用在线工具验证 JSON 格式正确性

---

## ⚙️ GitHub Actions 配置说明

### 工作流文件位置
`.github/workflows/update-lottery-data.yml`

### 定时任务配置
```yaml
schedule:
  - cron: '0 14 * * *'  # UTC 14:00 = 北京时间 22:00
```

### 修改运行时间
编辑 cron 表达式以更改运行时间：
- `0 14 * * *` - 每天 UTC 14:00（北京时间 22:00）
- `0 2,14 * * *` - 每天 UTC 02:00 和 14:00（北京时间 10:00 和 22:00）
- `0 */6 * * *` - 每 6 小时运行一次

### 依赖的 Python 包
- `requests` - HTTP 请求
- `beautifulsoup4` - HTML 解析

### 权限说明
工作流使用 `GITHUB_TOKEN` 自动提交更改，无需额外配置 secrets。

---

## 🔍 故障排查

### 问题：GitHub Actions 工作流未运行

**解决**:
1. 确认工作流文件已提交到仓库的 `main` 分支
2. 检查 Actions 页面是否启用（Settings > Actions > General）
3. 查看 Actions 标签页的运行历史和错误日志
4. 确认仓库有写入权限（Settings > Actions > General > Workflow permissions）

### 问题：网页不显示最新数据

**解决**:
1. 清除浏览器缓存
2. 检查 `lottery_history.json` 文件是否存在
3. 确认 JSON 格式正确（无语法错误）
4. 查看浏览器控制台错误信息
5. 确认 Vercel 已重新部署（查看 Vercel Dashboard）

### 问题：预测状态显示不正确

**解决**:
1. 确认 `target_period` > 最新开奖期号（未开奖）
2. 确认 `target_period` 格式与历史数据一致
3. 检查期号比较逻辑（字符串比较 vs 数字比较）

### 问题：历史预测不显示

**解决**:
1. 确认 `predictions_history.json` 文件存在
2. 确认文件中有 `predictions_history` 数组
3. 检查每条记录是否包含 `actual_result`
4. 确认 `hit_result` 已正确计算

---

## 📞 需要帮助？

如遇问题，请检查：
- GitHub Issues: 项目问题追踪
- DEPLOYMENT.md: 部署相关问题
- README.md: 项目总体说明
