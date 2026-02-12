# -*- coding: utf-8 -*-
"""测试单个模型的预测生成"""

import json
import os
import sys
from openai import OpenAI

# API 配置（通过环境变量设置）
BASE_URL = os.environ.get("AI_BASE_URL") or "https://aihubmix.com/v1"
API_KEY = os.environ.get("AI_API_KEY")
if not API_KEY:
    print("❌ 请设置环境变量 AI_API_KEY")
    sys.exit(1)

# 文件路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOTTERY_HISTORY_FILE = os.path.join(SCRIPT_DIR, "data", "lottery_history.json")
PROMPT_FILE = os.path.join(SCRIPT_DIR, "doc", "prompt2.0.md")

print("📄 加载 Prompt 模板...")
with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
    prompt_template = f.read()
print(f"✅ Prompt 模板加载成功 ({len(prompt_template)} 字符)\n")

print("📊 加载历史数据...")
with open(LOTTERY_HISTORY_FILE, 'r', encoding='utf-8') as f:
    lottery_data = json.load(f)
print(f"✅ 历史数据加载成功\n")

# 准备数据
next_draw = lottery_data.get("next_draw", {})
target_period = next_draw.get("next_period", "")
target_date = next_draw.get("next_date_display", "")
history_data = lottery_data.get("data", [])[:30]
history_json = json.dumps(history_data, ensure_ascii=False, indent=2)

print(f"🎯 目标期号: {target_period}")
print(f"📅 开奖日期: {target_date}\n")

# 构建 prompt
print("🔧 构建 Prompt...")
prompt = prompt_template.format(
    target_period=target_period,
    target_date=target_date,
    lottery_history=history_json,
    prediction_date="2025-11-18",
    model_id="SSB-Team-001",
    model_name="GPT-5"
)
print(f"✅ Prompt 构建成功 ({len(prompt)} 字符)\n")

# 保存 prompt 用于调试
with open('/tmp/test_prompt.txt', 'w', encoding='utf-8') as f:
    f.write(prompt)
print("💾 Prompt 已保存到 /tmp/test_prompt.txt\n")

# 调用 API
print("🤖 调用 GPT-5 模型...")
try:
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "你是一个专业的彩票数据分析师，擅长基于历史数据进行模式分析和预测。请严格按照要求返回 JSON 格式数据，不要有任何额外的解释或说明。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.8
    )

    response_text = response.choices[0].message.content.strip()
    print(f"✅ API 调用成功\n")

    # 保存原始响应
    with open('/tmp/test_response.txt', 'w', encoding='utf-8') as f:
        f.write(response_text)
    print("💾 响应已保存到 /tmp/test_response.txt\n")

    print("="*50)
    print("响应前500字符:")
    print("="*50)
    print(response_text[:500])
    print("="*50)

    # 尝试解析 JSON
    print("\n🔍 尝试解析 JSON...")

    # 提取 JSON
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        json_text = response_text[start:end].strip()
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        json_text = response_text[start:end].strip()
    else:
        json_text = response_text

    prediction_data = json.loads(json_text)
    print("✅ JSON 解析成功\n")

    print("="*50)
    print("预测数据概览:")
    print("="*50)
    print(f"期号: {prediction_data['target_period']}")
    print(f"日期: {prediction_data['prediction_date']}")
    print(f"模型: {prediction_data['model_name']}")
    print(f"预测组数: {len(prediction_data['predictions'])}\n")

    for pred in prediction_data['predictions']:
        print(f"组 {pred['group_id']}: {pred['strategy']}")
        print(f"  红球: {', '.join(pred['red_balls'])}")
        print(f"  蓝球: {pred['blue_ball']}")
        print()

    print("🎉 测试成功!")

except Exception as e:
    print(f"❌ 错误: {type(e).__name__}")
    print(f"   {str(e)}")
    import traceback
    traceback.print_exc()
