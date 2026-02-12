# 双色球开奖与 AI 预测数据展示系统 - Vercel 部署指南

## 🚀 部署到 Vercel

### 方法一：使用 Vercel CLI（推荐）

1. **安装 Vercel CLI**
   ```bash
   npm install -g vercel
   ```

2. **登录 Vercel**
   ```bash
   vercel login
   ```

3. **部署项目**
   ```bash
   cd Double-Color-Ball-AI
   vercel
   ```

4. **按照提示操作**：
   - Set up and deploy? **Yes**
   - Which scope? 选择你的账户
   - Link to existing project? **No**
   - What's your project's name? 输入项目名称（如 `lottery-ai`）
   - In which directory is your code located? **.**
   - Want to override the settings? **No**

5. **部署完成！** 🎉
   - Vercel 会给你一个 URL，类似：`https://lottery-ai.vercel.app`

### 方法二：使用 Vercel 网站（更简单）

1. **访问** [vercel.com](https://vercel.com)

2. **注册/登录账号**（可以用 GitHub 账号）

3. **点击 "Add New Project"**

4. **选择导入方式**：
   - **从 GitHub 导入**（推荐）：
     - 先将项目推送到 GitHub
     - 在 Vercel 中选择该仓库
     - 点击 Deploy

   - **或者使用 Vercel CLI**（见方法一）

5. **等待构建完成** ⏳

6. **访问你的网站！** 🌐

---

## 📋 部署前检查清单

✅ 确保所有文件已提交：
```bash
git add .
git commit -m "Ready for Vercel deployment"
```

✅ 确保项目结构正确：
```
├── index.html
├── css/
│   └── style.css
├── js/
│   ├── app.js
│   ├── data-loader.js
│   └── components.js
├── data/
│   ├── lottery_history.json
│   └── ai_predictions.json
├── vercel.json
└── .vercelignore
```

✅ 确保 `vercel.json` 配置文件存在

---

## 🔄 更新已部署的项目

### 自动部署（推荐）

如果你从 GitHub 导入，每次 push 代码到 GitHub，Vercel 会自动重新部署：

```bash
git add .
git commit -m "Update lottery data"
git push origin main
```

### 手动部署

使用 Vercel CLI：

```bash
vercel --prod
```

---

## 📊 更新数据

### 1. 更新历史开奖数据

在本地运行：
```bash
cd fetch_history
python3 fetch_lottery_history.py
```

然后更新 `data/lottery_history.json`：
```bash
# 复制并格式化数据
cp fetch_history/lottery_data.json data/lottery_history.json
```

记得添加 `last_updated` 字段到 JSON 文件。

### 2. 更新 AI 预测数据

编辑 `data/ai_predictions.json` 文件，添加新的预测。

### 3. 部署更新

```bash
git add data/
git commit -m "Update lottery data $(date +%Y-%m-%d)"
git push origin main
```

如果配置了自动部署，Vercel 会自动更新网站！

---

## 🌐 自定义域名（可选）

1. 在 Vercel 项目设置中点击 "Domains"
2. 添加你的自定义域名
3. 按照提示配置 DNS 记录

---

## ⚙️ Vercel 配置说明

`vercel.json` 文件配置了：

- ✅ 静态文件托管
- ✅ 路由规则
- ✅ 缓存控制（数据文件不缓存，确保总是最新）

### 缓存策略

- **HTML/CSS/JS**: 自动缓存优化
- **数据文件**: `max-age=0` 确保总是获取最新数据

---

## 🔧 环境变量（如果需要）

在 Vercel 项目设置中可以添加环境变量：

1. 进入项目设置 → Environment Variables
2. 添加变量名和值
3. 在代码中通过 `process.env.VARIABLE_NAME` 访问

---

## 📱 测试部署

部署后测试以下功能：

- ✅ 页面加载正常
- ✅ 主题切换工作
- ✅ Tab 切换正常
- ✅ 数据加载成功
- ✅ 响应式布局在移动端正常
- ✅ 预测命中计算正确

---

## 🐛 常见问题

### 1. 数据加载失败

**原因**: JSON 文件路径错误

**解决**: 确保 `data/` 目录在项目根目录，且文件名正确

### 2. 样式丢失

**原因**: CSS 文件路径错误

**解决**: 检查 `index.html` 中的 CSS 引用路径

### 3. 404 错误

**原因**: 路由配置问题

**解决**: 确保 `vercel.json` 配置正确

---

## 💰 Vercel 免费版限额

- ✅ 无限制的个人项目
- ✅ 100GB 带宽/月
- ✅ 自动 HTTPS
- ✅ 全球 CDN
- ✅ 自定义域名
- ✅ 自动部署

**对于这个项目完全够用！** 🎉

---

## 🔐 安全提示

- ✅ 不要在代码中包含敏感信息
- ✅ 数据文件是公开可访问的
- ✅ 定期更新依赖

---

## 📞 获取帮助

- Vercel 文档: https://vercel.com/docs
- Vercel 社区: https://github.com/vercel/vercel/discussions

---

## 🎉 部署成功后

分享你的网站链接：
- `https://your-project.vercel.app`
- 或者你的自定义域名

享受你的现代化双色球数据展示系统！✨
