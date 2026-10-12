#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 staging/ 生成 TVBox 可直接订阅的 tvbox.json。
   - 点播 sites：自研 spider（type3）+ 从采集到的完整配置中抽取
     type3(http 直链爬虫)/type0(json采集)/type1(xml采集)/type4(xpath)，
     跳过 csp_*（需 jar）和采集到的工具类 py（非 TVBox 爬虫）
   - 直播 lives：staging 里的 m3u/txt
   每次采集更新后运行并推送。用法：python3 gen_tvbox_json.py"""
import json, os, glob, re

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = "https://raw.githubusercontent.com/707214981/tvbox-sources/main"
SPLIT_BUDGET = 100000

def json5_loads(txt):
    """宽松解析：去 # 行注释、// 注释、尾随逗号"""
    body = "\n".join(l for l in txt.split("\n") if not l.strip().startswith("#"))
    body = re.sub(r'(?m)(?<!["\':])//.*$', '', body)
    body = re.sub(r',\s*([}\]])', r'\1', body)
    return json.loads(body)

def repo_parts(rel):
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
    for ln in lines:
        lb = len((ln + "\n").encode("utf-8"))
        if cur and cur_size + lb > SPLIT_BUDGET:
            parts.append(cur); cur, cur_size = [], 0
        cur.append(ln); cur_size += lb
    if cur:
        parts.append(cur)
    for i in range(len(parts)):
        out.append("staging/" + f"{base}.part{i+1}{ext}")
    return out

def short_name(entry):
    fn = os.path.splitext(os.path.basename(entry["file"]))[0]
    return fn.split("__", 1)[1] if "__" in fn else fn

def norm_api(api):
    """去代理前缀归一化，用于去重：ghfast.top/https://raw... -> https://raw..."""
    m = re.match(r'https?://[^/]+/(https?://.+|github\.com/.+)', api)
    if m:
        u = m.group(1)
        return u if u.startswith("http") else "https://" + u
    return api

def quote_url(url):
    import urllib.parse
    return urllib.parse.quote(url, safe=':/?#[]@!$&\'()*+,;=%')

def functional_ok(s, timeout=15):
    """功能实测：200 不代表能打开，必须真实调一次。
    type0/1 采集站：videolist 必须返回 >0 条影片；
    type3 py：能下载、编译通过、有 homeContent；
    type3 js：api 本身是规则则通过，否则必须有可下载的 ext。"""
    import urllib.request, re, json as _json
    UA = {"User-Agent": "Mozilla/5.0"}
    def get(url):
        req = urllib.request.Request(quote_url(url), headers=UA)
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.read()
    t, api = s.get("type"), str(s.get("api", ""))
    if t in (0, 1):
        sep = "&" if "?" in api else "?"
        data = get(api + sep + "ac=videolist&pg=1").decode("utf-8", "replace")
        n = len(re.findall(r"<video[\s>]", data))
        if not n:
            try:
                n = len(_json.loads(data).get("list", []))
            except Exception:
                pass
        return n > 0
    if t == 3:
        if api.endswith(".py"):
            data = get(api).decode("utf-8", "replace")
            if len(data) < 500:
                return False
            compile(data, "<spider>", "exec")
            return "def homeContent" in data
        data = get(api)
        if len(data) < 200:
            return False
        head = data[:4000].decode("utf-8", "replace")
        if "var rule" in head or "homeContent" in head or '"rule"' in head:
            return True  # api 本身就是规则
        ext = str(s.get("ext", ""))
        return bool(ext) and len(get(ext)) >= 200
    if t == 4:
        r = urllib.request.Request(quote_url(api), headers=UA, method="HEAD")
        return urllib.request.urlopen(r, timeout=timeout).status == 200
    return True

def main():
    sites, seen_api, seen_key = [], set(), set()

    def add_site(s):
        api = str(s.get("api", ""))
        key = str(s.get("key", ""))
        name = str(s.get("name", ""))
        if not api or not key or not name:
            return
        if "通知" in name and not s.get("searchable"):
            return  # 占位公告条目
        na = norm_api(api)
        if na in seen_api:
            return
        seen_api.add(na)
        if key in seen_key:  # key 冲突则加后缀
            i = 2
            while f"{key}_{i}" in seen_key:
                i += 1
            key = f"{key}_{i}"
            s = dict(s); s["key"] = key
        seen_key.add(key)
        sites.append(s)

    # 1) 自研 spiders
    for sp, name in [("spiders/91pornsm.py", "91PornSM"),
                     ("spiders/244544_yiren_fixed.py", "伊人网")]:
        if os.path.exists(os.path.join(BASE, sp)):
            add_site({"key": "py_" + os.path.splitext(os.path.basename(sp))[0],
                      "name": name, "type": 3, "api": RAW + "/" + sp,
                      "searchable": 1, "quickSearch": 1, "filterable": 1})

    # 2) 从采集到的完整配置中抽取可用站点
    n_cfg = 0
    for f in sorted(glob.glob(os.path.join(BASE, "staging", "vod", "txt", "*.txt")) +
                    glob.glob(os.path.join(BASE, "staging", "vod", "json", "*.json"))):
        try:
            c = json5_loads(open(f, encoding="utf-8", errors="replace").read())
        except Exception:
            continue
        if not isinstance(c, dict) or not c.get("sites"):
            continue
        n_cfg += 1
        for s in c["sites"]:
            if not isinstance(s, dict):
                continue
            t, api = s.get("type"), str(s.get("api", ""))
            if t == 3 and api.startswith("http"):
                add_site(s)                       # py/drpy/js 爬虫直链
            elif t in (0, 1) and api.startswith("http"):
                add_site(s)                       # json/xml 采集站
            elif t == 4:
                add_site(s)                       # xpath
            # csp_*（需 jar）跳过
    # 2b) 可达性过滤（自研 spider 不参与，始终保留）
    import concurrent.futures
    cand = sites[2:]
    print(f"解析配置: {n_cfg} 个，候选站点: {len(cand)}，逐个功能实测…")
    def _check(s):
        try:
            return s, functional_ok(s)
        except Exception:
            return s, False
    alive, dead = [], 0
    with concurrent.futures.ThreadPoolExecutor(16) as ex:
        for s, ok_ in ex.map(_check, cand):
            if ok_:
                alive.append(s)
            else:
                dead += 1
                print(f"  剔除: {s.get('key')} | {s.get('name','')[:24]}")
    sites = sites[:2] + alive
    print(f"实测结果: 保留 {len(alive)}，剔除 {dead}")

    # 3) 直播
    manifest = json.load(open(os.path.join(BASE, "staging", "manifest.json"), encoding="utf-8"))
    lives = []
    for e in manifest:
        if e["category"] not in ("live_m3u", "live_txt"):
            continue
        name = short_name(e)
        parts = repo_parts(e["file"])
        for idx, rp in enumerate(parts):
            nm = name if len(parts) == 1 else f"{name}-p{idx+1}"
            lives.append({"name": nm, "type": 0, "url": RAW + "/" + rp,
                          "ua": "Mozilla/5.0",
                          "epg": "http://epg.51zmt.top:8000/api/diyp/?ch={name}&date={date}"})

    from collections import Counter
    print("sites 类型分布:", dict(Counter(s["type"] for s in sites)))

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
    # 紧凑格式，控制体积（推送单参数上限约 127KB）
    json.dump(config, open(out, "w", encoding="utf-8"), ensure_ascii=False,
              indent=None, separators=(",", ":"))
    print(f"sites: {len(sites)}, lives: {len(lives)} -> {out}")

if __name__ == "__main__":
    main()
