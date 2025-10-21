#!/bin/bash

# Vercel 部署脚本

echo "=========================================="
echo "双色球数据展示系统 - Vercel 部署"
echo "=========================================="
echo ""

# 检查是否安装了 Vercel CLI
if ! command -v vercel &> /dev/null; then
    echo "⚠️  未检测到 Vercel CLI"
    echo ""
    echo "请先安装 Vercel CLI："
    echo "  npm install -g vercel"
    echo ""
    echo "或使用 Vercel 网站部署："
    echo "  https://vercel.com"
    exit 1
fi

# 检查是否已登录
echo "🔐 检查登录状态..."
if ! vercel whoami &> /dev/null; then
    echo "需要登录 Vercel 账号"
    vercel login
fi

echo ""
echo "📦 准备部署..."
echo ""

# 显示项目信息
echo "项目文件："
echo "  ✓ index.html"
echo "  ✓ css/style.css"
echo "  ✓ js/app.js"
echo "  ✓ js/components.js"
echo "  ✓ js/data-loader.js"
echo "  ✓ data/lottery_history.json"
echo "  ✓ data/ai_predictions.json"
echo "  ✓ vercel.json"
echo ""

# 询问部署类型
read -p "部署到生产环境? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 部署到生产环境..."
    vercel --prod
else
    echo "🧪 部署到预览环境..."
    vercel
fi

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "📝 提示："
echo "  - 访问 Vercel Dashboard 查看部署详情"
echo "  - 每次 git push 会自动重新部署"
echo "  - 更新数据后记得提交并推送"
echo ""
