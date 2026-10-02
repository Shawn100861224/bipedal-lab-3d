# 我是谁：给这个仓库的读者（和我自己）的一句话

这是郑州大学双足实验室招新第一轮考核的作业：一个「让我们认识你」的网页。
作者：肖宇航，郑州大学 2026 级软件工程，选的方向是 **3D（三维视觉 / 三维重建）**。

页面本身是 `index.html`，没有构建步骤、没有依赖、没有 CDN 字体——
双击就能打开，丢到 GitHub Pages 就能上线。

## 目录结构

```
index.html                 主页面（版式 + 文案 + 点云渲染 + 项目雷达）
data/projects.js           项目雷达的数据（window.__PROJECTS__，页面直接读取）
data/projects.json         同一份数据的纯 JSON（给别的程序用）
tools/fetch_projects.py    从 GitHub REST API 抓数据、过滤、分类、生成上面两个文件
tools/deploy_pages.sh      一键建仓库 + 推送 + 打开 GitHub Pages 设置
build/raw/projects.json    上一次抓取的原始结果（便于复查）
build/shots/*.png          桌面端 / 手机端截图（验收用）
```

## 刷新项目数据

```bash
export GITHUB_TOKEN="$(gh auth token)"     # 匿名额度只有 60 次/小时，会中途 403
python tools/fetch_projects.py             # 约 1 分钟，会打印抓到了多少、丢弃了哪些
```

脚本做三件事：

1. 拉 31 个手工列出的仓库详情（COLMAP / Open3D / nerfstudio / 3DGS / VGGT / DUSt3R / ORB-SLAM3 …）；
2. 用 16 组 topic 与关键词检索式补充新出现的仓库，按星标倒序；
3. 过滤掉「沾边但不属于三维视觉」的高星仓库（人脸识别、扫地机器人、求职资料、网页图形引擎…），
   给每个仓库算分类、星速（星标 ÷ 月龄），落盘成 `data/projects.js`。

想加自己的仓库：编辑脚本里的 `PICKED`（要中文推荐理由和安装命令）或 `SEARCHES`（检索式）。

## 部署（加分项）

```bash
bash tools/deploy_pages.sh      # 需要已登录的 gh CLI；会让你确认仓库名
```

或者手动：新建仓库 → 把这几个文件推上去 → Settings → Pages → 选 `main` 分支根目录。

## 验收记录（2026-10-02）

- `index.html` 在本地 `python -m http.server` 下打开，控制台无 JS 报错；
- 项目雷达渲染 116 张卡片，筛选 / 搜索 / 排序 / 展开安装命令 / 复制都可用；
- 手机端（390×844、414 宽）用 headless Chrome 截图检查过排版；
- 数据里每个仓库的星标都来自 GitHub API，抓取时间写在页面页脚。
