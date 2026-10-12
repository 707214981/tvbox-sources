#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 staging/manifest.json 生成 TVBox 可直接订阅的 tvbox.json。
   每次采集更新后运行，输出到仓库根 tvbox.json 并推送。
   用法：python3 gen_tvbox_json.py [--push]"""
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = "https://raw.githubusercontent.com/707214981/tvbox-sources/main"
SPLIT_BUDGET = 100000  # 与推送切分保持一致（按字节）

def repo_parts(rel):
    """本地 staging 相对路径 -> 仓库中的实际路径列表（大文件会被切分）"""
    full = os.path.join(BASE, "staging", rel)
    try:
        size = os.path.getsize(full)
    except OSError:
        return []
    if size <= SPLIT_BUDGET:
        return ["staging/" + rel]
    with open(full, encoding="utf-8", errors="replace") as f:
        lines = f.read().split("\n")
    parts, cur, cur_size, out = [], [], 0, []
    base, ext = os.path.splitext(rel)
    header = "#EXTM3U" if rel.endswith((".m3u", ".m3u8")) else None
    for ln in lines:
        lb = len((ln + "\n").encode("utf-8"))
        if cur and cur_size + lb > SPLIT_BUDGET:
            parts.append(cur); cur, cur_size = [], 0
        cur.append(ln); cur_size += lb
    if cur:
        parts.append(cur)
    for i, ls in enumerate(parts):
        out.append("staging/" + f"{base}.part{i+1}{ext}")
    return out

def short_name(entry):
    # "hujingguang-ChinaIPTV__Global.m3u8" -> "Global"
    fn = os.path.basename(entry["file"])
    fn = os.path.splitext(fn)[0]
    if "__" in fn:
        fn = fn.split("__", 1)[1]
    return fn

def main():
    manifest = json.load(open(os.path.join(BASE, "staging", "manifest.json"), encoding="utf-8"))
    sites, lives = [], []
    seen_keys = set()

    def add_site(key, name, stype, api):
        if key in seen_keys:
            return
        seen_keys.add(key)
        sites.append({"key": key, "name": name, "type": stype, "api": api,
                      "searchable": 1, "quickSearch": 1, "filterable": 1})

    # 1) 自研 spiders（type 3）
    for sp, name in [("spiders/91pornsm.py", "91PornSM"),
                     ("spiders/244544_yiren_fixed.py", "伊人网")]:
        if os.path.exists(os.path.join(BASE, sp)):
            add_site("py_" + os.path.splitext(os.path.basename(sp))[0], name, 3,
                     RAW + "/" + sp)

    # 2) 采集的点播
    for e in manifest:
        cat = e["category"]
        if cat not in ("vod_py", "vod_txt", "vod_json"):
            continue
        name = short_name(e)
        for rp in repo_parts(e["file"]):
            api = RAW + "/" + rp
            key = "auto_" + os.path.splitext(os.path.basename(rp))[0].replace(".", "_")
            if cat == "vod_py":
                add_site(key, name, 3, api)
            elif cat == "vod_txt":
                add_site(key, name, 0, api)
            else:
                add_site(key, name, 1, api)

    # 3) 直播
    for e in manifest:
        cat = e["category"]
        if cat not in ("live_m3u", "live_txt"):
            continue
        name = short_name(e)
        for idx, rp in enumerate(repo_parts(e["file"])):
            nm = name if idx == 0 and len(repo_parts(e["file"])) == 1 else f"{name}-p{idx+1}"
            lives.append({"name": nm, "type": 0, "url": RAW + "/" + rp,
                          "ua": "Mozilla/5.0", "epg": "http://epg.51zmt.top:8000/api/diyp/?ch={name}&date={date}"})

    config = {
        "sites": sites,
        "lives": lives,
        "parses": [
            {"name": "Json聚合", "type": 3, "url": "Demo"},
            {"name": "Web聚合", "type": 3, "url": "Web"},
        ],
        "rules": [
            {"name": "量子", "hosts": ["vip.lz", "hd.lz"], "regex": ["#EXT-X-DISCONTINUITY"]},
            {"name": "非凡", "hosts": ["vip.ffzy"], "regex": ["#EXT-X-DISCONTINUITY"]},
        ],
        "flags": ["youku", "qq", "iqiyi", "qiyi", "letv", "sohu", "tudou", "pptv",
                  "mgtv", "wasu", "bilibili", "renrenmi"],
        "ijk": [
            {"group": "软解码", "options": [
                {"category": 4, "name": "opensles", "value": "0"},
                {"category": 4, "name": "overlay-format", "value": "842225234"},
                {"category": 4, "name": "framedrop", "value": "1"},
                {"category": 4, "name": "soundtouch", "value": "1"},
                {"category": 4, "name": "start-on-prepared", "value": "1"}]},
            {"group": "硬解码", "options": [
                {"category": 4, "name": "opensles", "value": "0"},
                {"category": 4, "name": "overlay-format", "value": "842225234"},
                {"category": 4, "name": "framedrop", "value": "1"},
                {"category": 4, "name": "soundtouch", "value": "1"},
                {"category": 4, "name": "start-on-prepared", "value": "1"}]}
        ],
    }
    out = os.path.join(BASE, "tvbox.json")
    json.dump(config, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"sites: {len(sites)}, lives: {len(lives)} -> {out}")

if __name__ == "__main__":
    main()
