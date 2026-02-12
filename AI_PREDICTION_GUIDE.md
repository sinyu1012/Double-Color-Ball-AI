# AI 预测自动生成指南

## 功能说明

`generate_ai_prediction.py` 脚本可以自动调用多个 AI 模型生成双色球预测数据，并保存到 `data/ai_predictions.json`。

## 前置要求

### 1. 安装依赖

```bash
pip install openai
```

### 2. 配置 API

通过环境变量设置 API 配置：

```bash
export AI_API_KEY="your-api-key"
export AI_BASE_URL="https://aihubmix.com/v1"  # 可选，有默认值
```

或创建 `.env` 文件（参考 `.env.example`）。

## 使用方法

### 运行脚本

```bash
python3 generate_ai_prediction.py
```

### 执行流程

脚本会自动完成以下步骤：

1. **加载历史数据** - 从 `data/lottery_history.json` 读取最近 30 期开奖数据
2. **获取下期信息** - 从 `next_draw` 字段获取预测目标期号和日期
3. **调用 AI 模型** - 逐个调用配置的 AI 模型生成预测
4. **验证预测数据** - 检查返回的 JSON 格式是否正确
5. **创建备份** - 备份现有的 `ai_predictions.json`
6. **保存预测** - 将新预测保存到 `data/ai_predictions.json`

### 输出示例

```
==================================================
🤖 双色球 AI 预测自动生成
==================================================

📊 加载历史开奖数据...
🎯 目标期号: 25124
📅 开奖日期: 2025年10月28日
📝 历史数据: 最近 33 期

🔮 开始生成预测...

  ⏳ 正在调用 GPT-5 模型...
  ✅ GPT-5 预测成功
  ✓ 验证通过

  ⏳ 正在调用 Claude 4.5 模型...
  ✅ Claude 4.5 预测成功
  ✓ 验证通过

  ⏳ 正在调用 Gemini 2.5 模型...
  ✅ Gemini 2.5 预测成功
  ✓ 验证通过

  ⏳ 正在调用 DeepSeek R1 模型...
  ✅ DeepSeek R1 预测成功
  ✓ 验证通过

✅ 成功生成 4/4 个模型的预测

💾 保存预测数据...
  ✓ 已创建备份: ai_predictions_backup_20251027_152701.json
  ✓ 已保存到: data/ai_predictions.json

==================================================
🎉 预测生成完成！
==================================================
```

## 生成的数据格式

```json
{
  "prediction_date": "2025-10-27",
  "target_period": "25124",
  "models": [
    {
      "prediction_date": "2025-10-27",
      "target_period": "25124",
      "model_id": "SSB-Team-001",
      "model_name": "GPT-5",
      "predictions": [
        {
          "group_id": 1,
          "strategy": "热号追随者",
          "red_balls": ["09", "16", "17", "24", "25", "31"],
          "blue_ball": "13",
          "description": "选择最近高频号码，排除上一期号码"
        }
        // ... 共 5 组预测
      ]
    }
    // ... 共 4 个模型
  ]
}
```

## 预测策略说明

每个 AI 模型会生成 5 组预测，分别采用不同策略：

1. **热号追随者** - 选择最近 30 期高频号码（排除上一期）
2. **冷号逆向者** - 选择最近 30 期低频号码（奇偶比 3:3）
3. **平衡策略师** - 多维度平衡（奇偶/大小/和值/连号）
4. **周期理论家** - 短期频率上穿长期频率的号码
5. **综合决策者** - 融合以上所有策略

## 数据验证

脚本会自动验证生成的预测数据：

- ✓ 必需字段完整性（prediction_date, target_period, model_id, model_name, predictions）
- ✓ 预测组数量正确（5 组）
- ✓ 红球数量正确（6 个）
- ✓ 红球号码已排序
- ✓ 蓝球不为空

## 注意事项

### 1. API 调用限制

- 脚本会依次调用 4 个模型，请确保 API 有足够的调用配额
- 每次调用的 timeout 设置为 180 秒（3 分钟）
- 如果某个模型调用失败，会跳过该模型继续执行

### 2. 数据备份

- 每次运行脚本都会创建备份文件
- 备份文件命名格式：`ai_predictions_backup_YYYYMMDD_HHMMSS.json`
- 备份文件与原文件在同一目录

### 3. Prompt 优化

- Prompt 模板位于脚本中的 `PROMPT_TEMPLATE` 常量
- 可根据需要修改策略说明和要求
- 参考文档：`doc/prompt.md`

### 4. 模型配置

如需添加/修改模型：

```python
MODELS = [
    {
        "id": "模型 API ID",           # API 调用时使用的模型 ID
        "name": "显示名称",            # 前端显示的模型名称
        "model_id": "数据标识"         # JSON 中的 model_id 字段
    }
]
```

## 与现有工作流集成

### 自动化流程建议

1. **自动更新历史数据**
   ```bash
   cd fetch_history
   python3 fetch_lottery_history.py
   ```

2. **生成新预测**
   ```bash
   python3 generate_ai_prediction.py
   ```

3. **提交更改**
   ```bash
   git add data/lottery_history.json data/ai_predictions.json
   git commit -m "chore: update lottery data and AI predictions"
   git push
   ```

### GitHub Actions 集成示例

```yaml
name: Update Predictions

on:
  schedule:
    - cron: '0 15 * * 0,2,4'  # 周日、周二、周四 23:00 北京时间

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install requests beautifulsoup4 openai

      - name: Update lottery history
        run: |
          cd fetch_history
          python3 fetch_lottery_history.py

      - name: Generate AI predictions
        run: python3 generate_ai_prediction.py
        env:
          AI_API_KEY: ${{ secrets.AI_API_KEY }}
          AI_BASE_URL: ${{ secrets.AI_BASE_URL }}

      - name: Commit changes
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add data/
          git commit -m "chore: auto-update predictions" || exit 0
          git push
```

## 故障排查

### 问题：JSON 解析失败

**原因**：AI 返回的内容包含额外的说明文字

**解决**：
- 脚本已自动处理 ```json 标记
- 如仍有问题，请检查 Prompt 是否强调"只返回 JSON"
- 可调整 `extract_json_from_response` 函数

### 问题：验证失败

**原因**：返回的数据格式不符合要求

**解决**：
- 查看错误提示的具体字段
- 检查红球是否排序、数量是否正确
- 确认所有必需字段是否存在

### 问题：API 调用超时

**原因**：网络延迟或模型响应慢

**解决**：
- 增加 timeout 参数（默认 180 秒）
- 检查网络连接
- 分批运行（注释掉部分模型）

## 相关文件

- `generate_ai_prediction.py` - 主脚本
- `doc/prompt.md` - Prompt 模板文档
- `data/lottery_history.json` - 历史开奖数据（输入）
- `data/ai_predictions.json` - AI 预测数据（输出）

## 许可证

本脚本仅供学习交流使用，不构成任何投资建议。
