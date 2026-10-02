# -*- coding: utf-8 -*-
"""抓取 GitHub 上适合「3D = CV（三维视觉 / 三维重建）」方向的高热度项目。

数据来源：GitHub REST API（走 gh CLI 的已授权 token，5000 req/h）。
产出：
  data/projects.js   -> window.__PROJECTS__ = {...}   供 <script src> 直接加载（file:// 也能用）
  data/projects.json -> 同内容的纯 JSON
  build/raw/*.json   -> 原始响应，便于复查

用法：python tools/fetch_projects.py
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(ROOT, "build", "raw")
API = "https://api.github.com"


def token():
    t = os.environ.get("GITHUB_TOKEN")
    if t:
        return t.strip()
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return None


TOK = token()
HDRS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "lab-3d-radar/1.0",
}
if TOK:
    HDRS["Authorization"] = "token " + TOK


def get(path, params=None, retries=3):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8")), None
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            last = "HTTP %s %s" % (e.code, body)
            if e.code in (403, 429):
                print("  ! rate limited, sleep 20s (%s)" % last)
                time.sleep(20)
            else:
                break
        except Exception as e:  # noqa: BLE001
            last = repr(e)
            time.sleep(3)
    return None, last


# ---------------------------------------------------------------- 人工精选
# tier=picked：我逐条核过，写中文推荐理由 + 可执行的安装/试用命令
PICKED = [
    # (repo, 分类, 中文推荐理由, 安装/试用命令)
    ("colmap/colmap", "重建 SfM/MVS",
     "多视图重建的事实标准：SfM 求相机位姿、MVS 出稠密点云与网格。WSL 里就能装，小场景不吃显存，是「机器人眼睛」的起点。",
     "sudo apt update && sudo apt install -y colmap\n# 或源码编译: git clone https://github.com/colmap/colmap && cd colmap && mkdir build && cd build && cmake .. && make -j"),
    ("isl-org/Open3D", "点云与几何",
     "Python 处理点云/网格/可视化最省事的库，pip 一行装好，出图好看，适合做实验记录。",
     "pip install open3d\npython -c \"import open3d as o3d; print(o3d.__version__)\""),
    ("nerfstudio-project/nerfstudio", "神经渲染",
     "NeRF / 3DGS 一站式框架：训练、网页可视化、导出网格全都有。装它一个等于把神经渲染的流水线都拿到手。",
     "pip install nerfstudio\nns-train --help"),
    ("graphdeco-inria/gaussian-splatting", "3D 高斯泼溅",
     "3DGS 原论文官方实现，2023 年最重要的三维重建工作。先读它，再读各种改进版。",
     "git clone https://github.com/graphdeco-inria/gaussian-splatting --recursive"),
    ("nerfstudio-project/gsplat", "3D 高斯泼溅",
     "3DGS 的高效 CUDA 实现，训练速度和显存都明显优于原版，8GB 显存笔记本能跑小场景。",
     "pip install gsplat"),
    ("NVlabs/instant-ngp", "神经渲染",
     "Instant-NGP：用哈希编码把 NeRF 训练压到分钟级，理解「为什么能这么快」必读。",
     "git clone --recursive https://github.com/NVlabs/instant-ngp"),
    ("facebookresearch/pytorch3d", "点云与几何",
     "Meta 的可微渲染 + 3D 深度学习工具箱，写自己的三维网络时用来搭底座。",
     "pip install pytorch3d  # 建议按官网命令源码编译，匹配本机 CUDA"),
    ("naver/dust3r", "几何大模型",
     "DUSt3R：给两张图直接回归三维点图，不需要相机标定。2024 年三维重建范式的转折点。",
     "git clone --recursive https://github.com/naver/dust3r && pip install -r requirements.txt"),
    ("facebookresearch/vggt", "几何大模型",
     "VGGT：一次前向就吐出相机参数、深度、点云。2025 年最值得追的三维视觉基础模型，服务机器人感知的路线正确。",
     "git clone https://github.com/facebookresearch/vggt && pip install -r requirements.txt"),
    ("UZ-SLAMLab/ORB_SLAM3", "SLAM 与定位",
     "视觉惯性 SLAM 经典系统，机器人「我在哪」的标准答案之一，C++ 工程能力也顺带练了。",
     "git clone https://github.com/UZ-SLAMLab/ORB_SLAM3 --recursive"),
    ("gaoxiang12/slambook2", "SLAM 与定位",
     "《视觉 SLAM 十四讲》配套代码，中文教材里最适合入门的一条路径，每讲都能编译跑通。",
     "git clone https://github.com/gaoxiang12/slambook2"),
    ("cartographer-project/cartographer", "SLAM 与定位",
     "Google 的 2D/3D SLAM 建图系统，工程完整度高，看它怎么把研究者代码变成产品。",
     "git clone https://github.com/cartographer-project/cartographer"),
    ("PRBonn/kiss-icp", "SLAM 与定位",
     "极简 LiDAR 里程计，代码量小、精度高，适合拿来读「一个干净的 SLAM 系统长什么样」。",
     "pip install kiss-icp"),
    ("DepthAnything/Depth-Anything-V2", "深度与立体",
     "单目深度估计当前最常用的基线，机器人避障/抓取的第一手输入。",
     "git clone https://github.com/DepthAnything/Depth-Anything-V2 && pip install -r requirements.txt"),
    ("nianticlabs/monodepth2", "深度与立体",
     "自监督单目深度估计的经典工作，想懂「没标签怎么学深度」就看它。",
     "git clone https://github.com/nianticlabs/monodepth2"),
    ("facebookresearch/segment-anything", "感知与检测",
     "SAM：分割一切。机器人场景里做区域筛选、掩码标注的通用工具。",
     "pip install git+https://github.com/facebookresearch/segment-anything.git"),
    ("ultralytics/ultralytics", "感知与检测",
     "YOLO 系列开箱即用，检测/分割/姿态一套接口，做感知 demo 最快。",
     "pip install ultralytics"),
    ("open-mmlab/mmdetection3d", "感知与检测",
     "三维检测/点云检测工具箱，想系统学 3D 检测的模型族谱看这个仓库。",
     "pip install -U openmim && mim install mmengine mmcv mmdet3d"),
    ("PointCloudLibrary/pcl", "点云与几何",
     "C++ 点云库，机器人端滤波/配准/分割的标准件，和 ROS 搭配最常见。",
     "sudo apt install -y libpcl-dev pcl-tools"),
    ("cdcseacave/openMVS", "重建 SfM/MVS",
     "开源稠密重建（MVS）工具，输出点云和网格，和 COLMAP 常配对使用。",
     "git clone https://github.com/cdcseacave/openMVS"),
    ("openMVG/openMVG", "重建 SfM/MVS",
     "SfM 工具箱，代码结构清晰，适合对照 COLMAP 理解增量式重建。",
     "git clone --recursive https://github.com/openMVG/openMVG"),
    ("mikedh/trimesh", "点云与几何",
     "Python 网格处理轻量库，格式转换、去噪、算体积这类活它最顺手。",
     "pip install trimesh"),
    ("kornia/kornia", "点云与几何",
     "把相机模型、投影、可微 CV 算子都做成了 PyTorch 模块，写几何网络省的自己推公式。",
     "pip install kornia"),
    ("intelrealsense/librealsense", "感知与检测",
     "深度相机 SDK：想让机器人真的「看见」，迟早要碰硬件这一层。",
     "git clone https://github.com/IntelRealSense/librealsense"),
    ("NVlabs/FoundationPose", "感知与检测",
     "6D 物体位姿估计 + 跟踪的基础模型，抓取和装配任务的核心模块。",
     "git clone --recursive https://github.com/NVlabs/FoundationPose"),
    ("MrNeRF/awesome-3D-gaussian-splatting", "学习资源",
     "3DGS 论文/代码/数据集索引，跟踪这个方向前沿最快的一页纸。",
     "git clone https://github.com/MrNeRF/awesome-3D-gaussian-splatting"),
    ("autonomousvision/sdfstudio", "神经渲染",
     "神经表面重建框架，把「隐式表面 + 渲染」这套方法整理得很完整。",
     "git clone https://github.com/autonomousvision/sdfstudio"),
    ("hbb1/2d-gaussian-splatting", "3D 高斯泼溅",
     "2DGS：用二维高斯做曲面重建，法线和网格质量明显更好，写毕设/项目很好用。",
     "git clone https://github.com/hbb1/2d-gaussian-splatting --recursive"),
    ("facebookresearch/habitat-lab", "具身与机器人",
     "具身智能仿真环境（配合 habitat-sim），能在没有真机时练导航与视觉感知。",
     "git clone https://github.com/facebookresearch/habitat-lab && pip install -e habitat-lab"),
    ("YoYo000/MVSNet", "深度与立体",
     "深度学习 MVS 的经典实现，理解「多视图如何变深度图」从这里读起。",
     "git clone https://github.com/YoYo000/MVSNet"),
    ("Tencent-Hunyuan/Hunyuan3D-2", "生成式三维",
     "腾讯混元的图像转三维资产模型，能看出生成式三维和重建式三维的差别。",
     "git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2"),
]

# topic / 关键词检索（自动补充新出现的热门仓库）
SEARCHES = [
    ("topic:3d-reconstruction stars:>500", 12),
    ("topic:gaussian-splatting stars:>300", 12),
    ("topic:nerf stars:>500", 10),
    ("topic:neural-radiance-fields stars:>300", 8),
    ("topic:structure-from-motion stars:>200", 8),
    ("topic:point-cloud stars:>500", 12),
    ("topic:visual-slam stars:>400", 10),
    ("topic:slam stars:>800", 10),
    ("topic:depth-estimation stars:>300", 10),
    ("topic:multi-view-stereo stars:>150", 8),
    ("topic:3d-vision stars:>300", 10),
    ("topic:pose-estimation stars:>800", 8),
    ("topic:mesh-reconstruction stars:>150", 6),
    ("3d reconstruction in:name,description,readme stars:>800", 12),
    ("gaussian splatting created:>2025-01-01 stars:>150", 10),
    ("visual geometry transformer created:>2024-06-01 stars:>150", 6),
]

CATEGORY_RULES = [
    ("3D 高斯泼溅", ["gaussian-splat", "splatting", "3dgs", "splat", "gaussian-splatting"]),
    ("神经渲染", ["nerf", "radiance", "instant-ngp", "neural-render", "voxel"]),
    ("几何大模型", ["dust3r", "vggt", "mast3r", "foundation-model", "geometry-transformer", "monst3r"]),
    ("生成式三维", ["generation", "diffusion", "text-to-3d", "image-to-3d", "mesh-generation"]),
    ("重建 SfM/MVS", ["structure-from-motion", "sfm", "mvs", "colmap", "reconstruction", "photogrammetry"]),
    ("SLAM 与定位", ["slam", "odometry", "localization", "vio", "mapping", "lidar"]),
    ("深度与立体", ["depth", "stereo", "disparity", "monocular"]),
    ("点云与几何", ["point-cloud", "pointcloud", "mesh", "geometry", "rendering", "differentiable"]),
    ("感知与检测", ["detection", "segmentation", "pose", "tracking", "yolo", "sam", "perception", "camera"]),
    ("具身与机器人", ["embodied", "robot", "manipulation", "navigation", "humanoid", "simulation", "habitat"]),
    ("学习资源", ["awesome", "tutorial", "book", "course", "paper", "list"]),
]


RELEVANCE_KEYS = [
    "3d", "three-dimensional", "point cloud", "pointcloud", "gaussian splat", "splatting",
    "nerf", "radiance", "slam", "odometry", "depth", "stereo", "disparity", "reconstruction",
    "mesh", "sfm", "mvs", "photogrammetry", "camera", "geometry", "geometric", "voxel",
    "lidar", "volumetric", "rgb-d", "rgbd", "scene reconstruction", "neural render",
    "pose estimation", "sdf", "occupancy", "nerfstudio", "colmap", "point-cloud",
    "localization", "hloc", "vggt", "dust3r", "4d", "structure from motion", "6d pose",
]
BLACKLIST = [
    "mac-os-apps", "localai", "awesome-courses", "chatgpt", "llm", "langchain", "prompt-engineering",
    "cursor", "vscode", "neovim", "dotfile", "developer-roadmap", "coding-interview",
    "interview", "awesome-python", "free-programming", "public-apis", "build-your-own", "ai-agents",
]
# 自动检索会捞到「沾边但不属于三维视觉」的仓库，这里逐条否决（附原因，便于复查）
VETO = {
    "deepinsight/insightface": "人脸识别（二维），不是三维视觉",
    "lipku/livetalking": "数字人直播，属生成式视频",
    "amusi/ai-job-notes": "求职资料汇编",
    "deeplabcut/deeplabcut": "动物二维关键点",
    "makerspet/oomwoo": "扫地机器人整机项目",
    "mvig-sjtu/alphapose": "二维人体姿态",
    "playcanvas/engine": "网页图形引擎",
    "amusi/cvpr2026-papers-with-code": "论文清单，另收",
}


def relevant(repo):
    """自动检索回来的仓库必须真的属于三维视觉，否则丢掉（检索接口会夹带无关高星仓库）。"""
    name = repo["full_name"].lower()
    if name in VETO:
        return False
    desc = (repo.get("description") or "").lower()
    topics = [t.lower() for t in (repo.get("topics") or [])]
    hay = name + " " + desc + " " + " ".join(topics)
    if any(b in hay for b in BLACKLIST):
        return False
    return any(k in hay for k in RELEVANCE_KEYS)


def months_between(a, b):
    return max(1.0, (b - a).days / 30.44)


def category_of(full_name, desc, topics):
    """按关键词命中数打分归类：name/desc 命中 2 分，topic 命中 3 分（topic 更准）。"""
    name_l = full_name.lower()
    desc_l = (desc or "").lower()
    hay = name_l + " " + desc_l
    top = " ".join(t.lower() for t in (topics or []))
    if "awesome" in name_l or desc_l.startswith("a curated list") or desc_l.startswith("a list of"):
        return "学习资源"
    best, best_score = None, 0
    for cat, keys in CATEGORY_RULES:
        s = 0
        for k in keys:
            if k in hay:
                s += 2
            if k in top:
                s += 3
        if s > best_score:
            best, best_score = cat, s
    return best or "其他三维视觉"


def slim(repo, tier="auto", cat=None, why="", install=""):
    lic = (repo.get("license") or {}) or {}
    created = (repo.get("created_at") or "")[:10]
    updated = (repo.get("pushed_at") or "")[:10]
    stars = repo.get("stargazers_count", 0)
    per_month = 0.0
    try:
        c = datetime.strptime(created, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        per_month = stars / months_between(c, datetime.now(timezone.utc))
    except Exception:
        pass
    age_months = 0.0
    try:
        c = datetime.strptime(created, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        age_months = months_between(c, datetime.now(timezone.utc))
    except Exception:
        pass
    return {
        "full_name": repo["full_name"],
        "name": repo["name"],
        "owner": repo["owner"]["login"],
        "url": repo["html_url"],
        "homepage": repo.get("homepage") or "",
        "desc": (repo.get("description") or "").strip(),
        "stars": stars,
        "forks": repo.get("forks_count", 0),
        "issues": repo.get("open_issues_count", 0),
        "lang": repo.get("language") or "",
        "license": lic.get("spdx_id") or "NOASSERTION",
        "topics": repo.get("topics", [])[:12],
        "created": created,
        "updated": updated,
        "archived": bool(repo.get("archived")),
        "avatar": (repo.get("owner") or {}).get("avatar_url", ""),
        "star_per_month": round(per_month),
        "age_months": round(age_months),
        "hot": bool(age_months <= 30 and per_month >= 150),
        "tier": tier,
        "category": cat or category_of(repo["full_name"], repo.get("description"), repo.get("topics", [])),
        "why": why,
        "install": install,
    }


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(RAW, exist_ok=True)
    if not TOK:
        print("!! 没有 GitHub token，匿名额度只有 60 req/h，可能中途被限流")

    by_name = {}

    print("[1/2] 拉取精选仓库 %d 个 ..." % len(PICKED))
    for full, cat, why, install in PICKED:
        repo, err = get("/repos/" + full)
        if not repo:
            print("  x %-42s %s" % (full, err))
            continue
        if repo.get("archived"):
            print("  ~ %-42s 已归档，仍收录" % full)
        by_name[full.lower()] = slim(repo, tier="picked", cat=cat, why=why, install=install)
        print("  + %-42s %6d stars  %s" % (full, repo["stargazers_count"], cat))
        time.sleep(0.15)

    print("[2/2] topic / 关键词检索补充 ...")
    errors = []
    for q, per in SEARCHES:
        res, err = get("/search/repositories", {"q": q, "sort": "stars", "order": "desc", "per_page": per})
        if not res:
            print("  x %-50s %s" % (q, err))
            errors.append({"q": q, "err": err})
            continue
        items = res.get("items", [])
        print("  = %-50s %d 条" % (q, len(items)))
        for r in items:
            fn = r["full_name"].lower()
            if fn in by_name:
                continue
            if r.get("archived") or r.get("stargazers_count", 0) < 100:
                continue
            if not relevant(r):
                print("    - 丢弃无关: %s (%d stars)" % (r["full_name"], r["stargazers_count"]))
                continue
            by_name[fn] = slim(r)
        time.sleep(2.2)  # 检索接口 30 req/min

    items = sorted(by_name.values(), key=lambda x: -x["stars"])
    cats = {}
    for it in items:
        cats[it["category"]] = cats.get(it["category"], 0) + 1

    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z"),
        "source": "GitHub REST API",
        "query_count": len(SEARCHES) + len(PICKED),
        "total": len(items),
        "picked": sum(1 for i in items if i["tier"] == "picked"),
        "hot": sum(1 for i in items if i["hot"]),
        "categories": cats,
        "errors": errors,
        "items": items,
    }

    with open(os.path.join(RAW, "projects.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    js = json.dumps(payload, ensure_ascii=False, indent=1)
    js = js.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").replace("</", "<\\/")
    with open(os.path.join(DATA, "projects.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=1))
    with open(os.path.join(DATA, "projects.js"), "w", encoding="utf-8") as f:
        f.write("/* 由 tools/fetch_projects.py 生成，数据源 GitHub REST API */\n")
        f.write("window.__PROJECTS__ = " + js + ";\n")

    print("\n完成：%d 个仓库（精选 %d），生成 %s" % (len(items), payload["picked"], payload["generated_at"]))
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print("   %-12s %d" % (c, n))
    top = items[:8]
    print("Top8: " + ", ".join("%s(%d)" % (t["name"], t["stars"]) for t in top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
