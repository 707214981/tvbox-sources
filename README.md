# tvbox-sources

TVBox 点播 / 直播源聚合仓库。每天 06:00（CST）自动从 GitHub 公开源仓库采集、校验并抽查可用性后更新。

## 📺 直接订阅

把下面这个地址填进 TVBox 的「配置地址」，即可使用全部源：

```
https://raw.githubusercontent.com/707214981/tvbox-sources/main/tvbox.json
```

`tvbox.json` 包含点播 `sites`（py 爬虫 / JSON·XML 采集站）和直播 `lives`（m3u / txt）。每次更新前都会逐个实测：采集站必须真实返回影片数据、py 爬虫必须能下载编译、js 规则必须是真规则——打不开的会被自动剔除。

## 📁 目录结构

```
tvbox-sources/
├── tvbox.json                  # TVBox 可直接订阅的配置（每天自动重新生成）
├── README.md                   # 本文件
│
├── spiders/                    # 点播爬虫脚本（TVBox type 3 直接引用）
│   ├── 91pornsm.py             # 自研：91PornSM（14 分类，封面 AES 解密）
│   ├── 伊人网.py   # 自研：伊人网 18yiren.tv（匿名 API 接口族；域名高频迁移，已做自适应——自动跟随符合 www.<6位数字>.xyz 格式的新域名）
│   ├── ...                     # 第三方验证可用的 py / js 爬虫约 195 个
│   └── index.json              # 文件名 → 展示名的映射表
│
├── spider-agent/
│   └── AGENTS.md               # TVBox 爬虫开发手册（给 AI 模型看的逆向/开发规范）
│
├── staging/                    # 从上游仓库采集的原始资源文件
│   ├── vod/py/                 # 点播 py 脚本（采集自 GitHub，多为工具类脚本供参考）
│   ├── vod/json/               # 点播 JSON 配置（多为完整 TVBox 配置，用于抽取站点）
│   ├── vod/txt/                # 点播 txt（同上，多为完整配置）
│   ├── live/m3u/               # 直播 m3u / m3u8 源
│   ├── live/txt/               # 直播 txt 源（`名称,url` 格式）
│   ├── manifest.json           # 采集清单：每个文件的来源仓库、原始路径、大小、
│   │                           # 校验结果、直播流抽查结果（stream_test）、更新时间
│   └── stream_samples.json     # 每个直播源抽查用的 sample 流地址（抽查脚本输入）
│
├── tools/                      # 采集 / 生成 / 导入脚本（GitHub Actions 调用）
│   ├── collect.py              # 采集：clone 上游仓库，按清单拷贝并校验到 staging/
│   ├── gen_tvbox_json.py       # 生成：实测全部候选站点，生成 tvbox.json
│   ├── test_streams.py         # 抽查：每个直播源抽测最多 8 条流，结果写回 manifest
│   ├── import_spiders.py       # 一次性导入：按 spider_import.json 下载第三方爬虫
│   ├── spider_import.json      # 第三方爬虫导入清单（195 个已验证源的地址与名称）
│   └── extra_sites.json        # 手工精选的采集站（生成器会一并实测后加入）
│
└── .github/workflows/
    └── daily.yml               # 每日自动更新工作流（见下）
```

文件名格式：`{上游owner}-{repo}__{原文件路径}`，例如
`hujingguang-ChinaIPTV__USA.m3u8`，可追溯来源。
大文件会被按行切分为 `*.partN.*`（TVBox 侧同样可用，`tvbox.json` 中的直播地址已对应）。

## 🔢 tvbox.json 里的 type 说明

| type | 含义 | 例子 |
|---|---|---|
| 0 | 苹果 CMS **JSON** 采集接口 | `https://360zy.com/api.php/provide/vod` |
| 1 | 苹果 CMS **XML** 采集接口 | `https://api.okzyw.net/.../at/xml` |
| 3 | 爬虫脚本（py / drpy js） | `spiders/` 下的文件 |
| 4 | xpath 规则站 | — |

> 生成器会实测接口**实际返回的格式**来校正 type（很多上游配置把返回 JSON 的站错标成 type 1）；
> 有些站 http 返回 XML、https 返回 JSON，只有返回格式一致时才会切换到 https。

## 🤖 自动更新（GitHub Actions）

`.github/workflows/daily.yml` 每天 06:00（CST）自动运行：

1. **采集** `tools/collect.py` — 重新 clone 上游仓库，拷贝并校验新文件
2. **抽查** `tools/test_streams.py` — 每个直播源抽测最多 8 条流
3. **生成** `tools/gen_tvbox_json.py` — 实测全部候选站点，重新生成 `tvbox.json`
4. **提交** — 有变化则自动 commit + push

也可在仓库 **Actions** 页面手动触发（Run workflow）：
- task = `daily`：立即执行一次每日更新
- task = `import-spiders`：一次性导入 `tools/spider_import.json` 清单里的第三方爬虫

## 📦 上游源仓库

| 仓库 | 采集内容 |
|---|---|
| adminouyang/231006 | py 点播脚本、点播/直播 txt |
| royalhayga/tvbox-master-aggregator | tvbox.json 点播配置 |
| gaotianliuyun/gao | js.json 点播配置（约 300 站点） |
| hujingguang/ChinaIPTV | m3u8 直播源 |
| dongyubin/IPTV | 直播源 |
| yy-niuma/live-tv | M3U 直播聚合 |
| joevess/IPTV | m3u8 / txt 直播源 |
| iptv-org/iptv | 中国区 m3u 直播（cn / cn_cctv） |
| qist/tvbox | dianshi.json（153 站点配置）+ ITV.txt 直播 |
| hkuc/tvbox-config | tv/ 多家配置聚合 |
| wxadxmyz/muhai-tvbox-sources | 清理过的点播配置 |
| cjj200011222/tvbox-source | api.json（100 站点配置） |
| 1771245847/TvBox | 10 个点播配置文件 |
| best-fan/iptv-sources | 每日构建的 m3u8（全量/央视/省份） |
| ngo5/IPTV | m3u 直播（v4/v6 双栈） |
| 4yt1k/m3u-autoupdate | 测速聚合的 m3u/txt 直播 |
| phu889/kjh998 | py 点播脚本（195 个已导入 spider 的源头） |
| IY-CPU/IY | iy 系列点播 json 配置 + txt |

第三方爬虫另见 `tools/spider_import.json`（195 个，来源为公开分享的 TVBox 配置）。

## ⚠️ 说明

- 直播流抽查为**采样探测**（每个源最多抽 8 条），仅代表抽查时刻的连通性，不保证全部频道 24 小时可用。
- 点播站点的可用性每次生成前都会实测，但源站随时可能失效；遇到打不开的源，下次自动更新时会剔除。
- 所有资源均来自 GitHub 公开仓库，仅做聚合索引与可用性抽查，版权归原作者所有。
