#!/usr/bin/env bash
# 把当前目录发布到 GitHub Pages（静态页直发，不用 GitHub Actions、不用构建）
#
# 为什么这么写：对照过 web-deploy-github 技能自带的 deploy_github_pages.sh，它有两个硬伤 ——
#   1) 它把 Pages 的源指到 gh-pages 分支，但它自己并不创建这个分支，也不生成 Actions 工作流
#      （工作流只有它的 init_project.sh 才会写），结果就是这个静态页永远 404；
#   2) 它用 `|| echo 警告` 把 Pages 配置失败吞掉，出问题时你只会看到一句"可能已配置"。
# 这份脚本的做法：把 Pages 源设成 main 分支根目录（build_type=legacy，纯静态不需要构建），
# 配置失败就明确报错，最后轮询真实 URL 直到返回 200 才算成功。
#
# 用法：bash tools/deploy_pages.sh [仓库名]        默认：bipedal-lab-3d
set -euo pipefail

REPO_NAME="${1:-bipedal-lab-3d}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

say() { printf '\n==> %s\n' "$*"; }

say "检查 gh 登录状态"
gh auth status >/dev/null 2>&1 || { echo "请先跑：gh auth login"; exit 1; }
OWNER="$(gh api user -q .login)"
GH_EMAIL="$(gh api user -q '.email // empty' 2>/dev/null || true)"
[ -n "${GH_EMAIL:-}" ] || GH_EMAIL="${OWNER}@users.noreply.github.com"
echo "    账号 $OWNER    仓库 $OWNER/$REPO_NAME"

say "检查必备文件"
for f in index.html data/projects.js data/projects.json; do
  [ -f "$f" ] || { echo "缺少 $f —— 先运行 python tools/fetch_projects.py"; exit 1; }
done

# 只发布网页需要的文件：build/ 是本地调试产物（截图、临时页），不上线
cat > .gitignore <<'EOF'
build/
__pycache__/
EOF

say "初始化 git 仓库（分支固定为 main）"
[ -d .git ] || git init -q
git symbolic-ref HEAD refs/heads/main
git config user.name "$OWNER"
git config user.email "$GH_EMAIL"
git add -A
if git diff --cached --quiet; then
  echo "    （没有新改动）"
else
  git commit -q -m "个人页：3D（三维视觉）方向 + 三维视觉开源项目雷达"
  echo "    已提交"
fi

say "创建 / 推送远程仓库"
if gh repo view "$OWNER/$REPO_NAME" >/dev/null 2>&1; then
  echo "    仓库已存在，改用推送"
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO_NAME.git"
  git push -u origin main
else
  gh repo create "$REPO_NAME" --public --source=. --remote=origin --push \
    --description "双足实验室第一轮考核：3D（三维视觉 / 三维重建）方向个人页 + 三维视觉开源项目雷达"
fi

say "把 Pages 指向 main 分支根目录（纯静态，不需要构建）"
for attempt in 1 2 3; do
  if [ "$attempt" = "1" ]; then
    gh api -X POST "/repos/$OWNER/$REPO_NAME/pages" \
      -f build_type=legacy -f 'source[branch]=main' -f 'source[path]=/' >/dev/null 2>&1 && break
  else
    gh api -X PUT "/repos/$OWNER/$REPO_NAME/pages" \
      -f build_type=legacy -f 'source[branch]=main' -f 'source[path]=/' >/dev/null 2>&1 && break
  fi
  sleep 3
done
PAGES_JSON="$(gh api "/repos/$OWNER/$REPO_NAME/pages" 2>/dev/null || true)"
if [ -z "$PAGES_JSON" ]; then
  echo "    !! 自动配置失败：请手动打开下面地址，Source 选 main / (root)，保存后再运行本脚本"
  echo "    https://github.com/$OWNER/$REPO_NAME/settings/pages"
  exit 2
fi
echo "    Pages 状态：$(printf '%s' "$PAGES_JSON" | python -c 'import sys,json;d=json.load(sys.stdin);print(d.get("status"), d.get("html_url"), (d.get("source") or {}))' 2>/dev/null || echo "$PAGES_JSON" | head -c 200)"

SITE="https://$OWNER.github.io/$REPO_NAME/"

say "把仓库地址写回页脚（免得留一句"部署后补链接"）"
python - "$SITE" "$OWNER/$REPO_NAME" <<'PY'
import re, sys
site, slug = sys.argv[1], sys.argv[2]
p = "index.html"
s = open(p, encoding="utf-8").read()
s = re.sub(r'<a id="repoLink"[^>]*>.*?</a>', '<a id="repoLink" href="https://github.com/%s" target="_blank" rel="noopener">github.com/%s</a>' % (slug, slug), s)
open(p, "w", encoding="utf-8").write(s)
print("    index.html 已更新：", site)
PY
git add -A && { git diff --cached --quiet || git commit -q -m "页脚补上仓库与站点链接"; }
git push -q origin main

say "等待站点上线（最多 3 分钟）"
CODE=000
for i in $(seq 1 18); do
  CODE="$(curl -s -o /dev/null -w '%{http_code}' -m 15 "$SITE" || echo 000)"
  printf '    第 %2d 次检查：HTTP %s\n' "$i" "$CODE"
  [ "$CODE" = "200" ] && break
  sleep 10
done

if [ "$CODE" = "200" ]; then
  echo
  echo "上线成功：$SITE"
  echo "抽查数据文件：HTTP $(curl -s -o /dev/null -w '%{http_code}' -m 15 "${SITE}data/projects.js")"
  echo "首页标题：$(curl -s -m 20 "$SITE" | grep -o '<title>[^<]*' | head -1)"
else
  echo
  echo "站点还没就绪（HTTP $CODE）。常见原因：首次构建要 1-2 分钟，或 Pages 需手动确认。"
  echo "手动入口：https://github.com/$OWNER/$REPO_NAME/settings/pages"
  exit 3
fi
