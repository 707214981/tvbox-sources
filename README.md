# tvbox-sources

TVBox 点播源与直播源每日采集。每天自动从 GitHub 公开源仓库抓取、校验并抽查可用性后更新。

## 目录

| 目录 | 内容 |
|---|---|
| `vod/py/` | 点播 py 爬虫脚本 |
| `vod/json/` | 点播 JSON 配置 |
| `vod/txt/` | 点播源 txt |
| `live/m3u/` | 直播源 m3u / m3u8 |
| `live/txt/` | 直播源 txt |
| `manifest.json` | 全部文件的来源、上次更新时间、校验与抽查结果 |

文件名格式：`{源仓库owner}-{repo}__{原路径}`，可追溯来源。

## 数据说明

- `manifest.json` 中每条记录包含：来源仓库、原始路径、文件大小、校验结果、直播流抽查结果（`stream_test.ok/tested`）、更新时间。
- 直播流抽查为采样探测（每个源最多抽 8 条），仅代表抽查时刻的连通性，不保证全部频道可用。
- 所有源均来自 GitHub 公开仓库，仅做聚合索引与可用性抽查，版权归原作者所有。

## 源仓库

- adminouyang/231006 — py 点播脚本、点播/直播 txt
- royalhayga/tvbox-master-aggregator — tvbox.json 点播配置
- hujingguang/ChinaIPTV — m3u8 直播源
- dongyubin/IPTV — 直播源
- yy-niuma/live-tv — M3U 直播聚合

更新时间见 `manifest.json`。

## 自动更新（GitHub Actions）

- 每天 06:00（CST）自动运行 `.github/workflows/daily.yml`：采集上游源 → 抽查直播流 → 重新生成 `tvbox.json` → 提交推送，全程无需人工批准。
- 采集与生成脚本在 `tools/`（`collect.py` / `gen_tvbox_json.py` / `test_streams.py`），可在 Actions 页面手动触发（Run workflow）立即执行一次；选择 task=import-spiders 可一次性导入 `tools/spider_import.json` 清单里的第三方 spider。
