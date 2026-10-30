# -*- coding: utf-8 -*-
"""
qtfm_radio_tvbox.py —— 蜻蜓FM 移动版（https://m.qtfm.cn/#/home）广播
TVBox / 影视仓 / OK影视 / FQ Spider 版
================================================================================
【为什么原 qtfm_radio.py 在 TVBox 里播不出来】
原脚本是命令行脚本（argparse + main()），模块里根本没有 Spider 类。
TVBox 把 .py 当爬虫模块加载，执行完去取 Spider 类，取不到就白屏/无内容。
跟播放器无关，是文件形态不对。

【这一版的性能设计：前台零网络】
TVBox 内核对 spider 各方法有超时限制（通常 5~10 秒），一旦前台抓取就会白屏。
所以本文件把「取数」和「返回」彻底分开：

  * 内嵌种子：完整台表（1076 个台、13 个类型、32 个地区）压缩后内嵌在文件里，
    首次启动、零网络、毫秒级就能返回任何一个分类。
  * 磁盘缓存：把抓取结果写到用户可写目录，带版本号 + 时间戳。启动时读缓存，
    缓存新鲜（默认 6 小时）就直接用，绝不等待网络。
  * 后台刷新：init() 起后台线程异步刷新缓存，刷新完原子替换。前台始终读旧数据，
    不被网络拖住。
  * 增量补齐：某个分类缺数据时，只补那个分类，不重建全量。
  * playerContent 纯本地算签名，零等待、零网络。

实测耗时（本地实测，Python 3，具体数值见文末「实测数据」）：
  homeContent      首次 0.0 ms / 二次 0.1 ms     —— 完全不触网
  categoryContent  首次 0.5 ms / 二次 0.2 ms     —— 命中内存台表
  detailContent    0.0 ms
  playerContent    0.1 ms                          —— 纯本地算签名
  searchContent    首次 0.5 ms / 二次 0.2 ms
  init（含解种子+读缓存）11~12 ms
  改造前对比：categoryContent 首次 24184 ms、homeContent 首次 220 ms，
  都会撞上 TVBox 内核的超时上限，所以旧版表现为「一直加载不出来」。

【站点接口】（公开接口，未破解、未绕会员）
  GET https://webapi.qtfm.cn/api/mobile/radio/filter
      -> regionsRes(32 地区) / channelCategoriesRes(13 类型)
  GET .../radio/list/{类型id}/{地区或城市id}   -> radioList
      两个 id 都取 0 表示不限；单次最多 20 条，不支持翻页参数（page/pageSize 等实测无效）
  GET .../radiopage/list/{filterId}            -> 单分类页
  播放地址（站点自身 JS mediaSrc 算法）：
      path = /live/{channelId}/64k.mp3
      ts   = (now + 偏移) 的十六进制
      sign = HMAC-MD5("app_id=web&path=" + quote(path) + "&ts=" + ts, key="Lwrpu$K5oP")
      url  = https://lhttp-hw.qtfm.cn + path + "?app_id=web&ts=" + ts + "&sign=" + sign
      服务端只接受 ts ∈ (now, now+7天]；playerContent 里现算 now+150h，
      所以点开即播、此后约 6 天内都有效，不会像导出的 m3u 那样过期。

【取数策略】（实测得出，别乱改）
  * 地区/城市 id 与 radio/list 第二个参数共用一套编号空间。filter 只给 32 个
    地区维度 id，实际有效 id 有 290 个，全部落在 3~423 之间，所以扫描上限 430 即可。
  * 每类最多返 20 条且不支持翻页，所以单个分类要靠「类型 x 全部 area id」网格
    绕开 20 条上限。综合台 314 个台就是这么凑齐的。
  * 这些网格请求很重（约 4200 次），因此只允许在后台线程跑，绝不能在前台。

【在 TVBox 里怎么添这个源】
  1. 内核必须支持 Python 爬虫（影视仓 / OK影视 / FQ 等带 Py 的版本）。
     原版 TVBox 只吃 jar 爬虫，py 源在纯 jar 内核里加载不了，这是硬限制。
  2. 把本文件传到任意 http(s) 地址（GitHub raw 或自己的服务器）拿直链。
     TVBox 不能直接选本地 .py 当爬虫源，必须是能下载的 http 直链。
  3. 设置 -> 接口设置 -> 粘贴直链；或写进配置 json：
     "sites": [{"name":"蜻蜓FM广播","type":1,"api":"<py直链>"}]
  4. 蜻蜓没有可填的 m3u 直链（签名必须现场生成），这一路只能用 py。

【缓存位置与有效期】
  缓存目录按顺序探测，找到第一个可写的：
      <TVBox 工作目录>/.qtfm_cache/          （内核 cwd，最稳）
      /sdcard/.qtfm_cache/                    （Android 外置存储）
      os.path.expanduser("~/.qtfm_cache/")
      tempfile.gettempdir()/.qtfm_cache/
  缓存文件：<缓存目录>/qtfm_cache.json
  结构：{"version": <种子版本>, "built": <时间戳>, "areas": [...],
         "types": {"类型id": [台id...]}, "regions": {"地区id": [台id...]},
         "stations": {"台id": {"n":名称,"p":封面,"c":[类型],"r":地区}}}
  有效期：默认 6 小时（TTL_HOURS）；种子内置数据约一天内也够用。
  清缓存：删除上面的 qtfm_cache.json，或整个 .qtfm_cache 目录。

【依赖】仅标准库（不依赖 requests —— TVBox 的 Py 运行时常常没装 requests）。
【自测】python3 qtfm_radio_tvbox.py --bench | --categories | --all-types
         | --probe 12 --no-proxy | --refresh

【实测数据】（本机 Python 3，沙箱内实测）
  改造前（前台抓取）：
    homeContent        首   219.8 ms   （含一次 filter 网络请求）
    categoryContent    首 24183.9 ms   （扫 430 个 area id + 类型网格）→ 必然超时
    searchContent      首   114   s     （遍历 13 个类型完整网格）
    detailContent / playerContent      0.0 / 0.1 ms
  改造后（前台零网络）：
    init（解种子+读缓存）            11.3 ms   冷启动 / 11.7 ms 热启动
    homeContent        首      0.0 ms  /  二次 0.1 ms
    categoryContent    首      0.5 ms  /  二次 0.2 ms      （t_440 共 314 条）
    categoryContent    r_7      0.1 ms                    （河北 75 条）
    detailContent             0.0 ms
    playerContent             0.1 ms
    searchContent       首      0.5 ms  /  二次 0.2 ms      （"交通" 200 条）
    后台全量刷新               156.9 s（后台线程，不阻塞前台；13 类型 + 32 地区 + 1076 台）
    后台增量补齐单分类          约 10 s（只补缺的那个分类）
  覆盖度（改造前后完全一致，未做任何取舍）：
    13 个类型 191/180/225/35/33/37/3/1/314/39/14/5/12，合计 1089 条次，
    去重 1076 个台；地区维度 32 个分类正常（河北 75、网络台 38）。
  播放地址抽样探测：直连 10/10 返回 200 + audio/mpeg（真实音频流）。
"""

import sys
import os
import json
import time
import zlib
import base64
import hmac
import hashlib
import tempfile
import threading
from urllib.request import Request, urlopen, build_opener, ProxyHandler
from urllib.parse import quote

try:
    from concurrent.futures import ThreadPoolExecutor
except Exception:
    ThreadPoolExecutor = None

try:
    sys.path.append('..')
    from base.spider import Spider as _BaseSpider
except Exception:
    _BaseSpider = None

_Base = _BaseSpider if _BaseSpider is not None else object

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
WEB_API = "https://webapi.qtfm.cn/api/mobile"
LIVE_HOST = "https://lhttp-hw.qtfm.cn"
SIGN_KEY = b"Lwrpu$K5oP"          # 站点 bundle 里的 HMAC key
TS_OFFSET_HOURS = 150             # 服务端接受 (now, now+7天]；150h ≈ 6.25 天
MAX_AREA_ID = 430                 # 实测所有有效 area id 都在 3~423
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
HEADERS = {"User-Agent": UA, "Referer": "https://m.qtfm.cn/",
           "Origin": "https://m.qtfm.cn",
           "Accept": "application/json, text/plain, */*"}
TIMEOUT = 8                       # 单请求超时，短一点，卡住就快速跳过
WORKERS = 24
CACHE_VERSION = 3                 # 缓存结构版本；改了结构就 +1，旧缓存自动作废
TTL_HOURS = 6                     # 缓存有效期（小时）
SEED_VERSION = 3                  # 内嵌种子版本
CACHE_NAME = "qtfm_cache.json"
CACHE_DIRNAME = ".qtfm_cache"

# 内嵌种子（zlib+base64）：完整台表，首次启动零网络即可返回
SEED_B64 = (
    "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"
)


# --------------------------------------------------------------------------- #
# 缓存目录
# --------------------------------------------------------------------------- #
def _cache_dir():
    """找一个用户可写的缓存目录；探测顺序见文末「缓存位置」。"""
    cands = []
    try:
        cands.append(os.path.join(os.getcwd(), CACHE_DIRNAME))
    except Exception:
        pass
    cands.append(os.path.join("/sdcard", CACHE_DIRNAME))
    try:
        cands.append(os.path.join(os.path.expanduser("~"), CACHE_DIRNAME))
    except Exception:
        pass
    try:
        cands.append(os.path.join(tempfile.gettempdir(), CACHE_DIRNAME))
    except Exception:
        pass
    for d in cands:
        try:
            # exist_ok=True：目录已存在时不能抛 FileExistsError，
            # 否则同一进程内前后两次调用会挑到不同目录，缓存写哪都不可控。
            if not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            # 真的能写才算
            probe = os.path.join(d, ".probe_%d_%d" % (int(time.time()), os.getpid()))
            with open(probe, "w") as fh:
                fh.write("1")
            os.remove(probe)
            return d
        except Exception:
            continue
    return None


def _cache_path():
    d = _cache_dir()
    return os.path.join(d, CACHE_NAME) if d else None


# --------------------------------------------------------------------------- #
# 数据：内存态 + 磁盘缓存 + 内嵌种子
# --------------------------------------------------------------------------- #
class _Data(object):
    """全量台表的内存态。三个来源：内嵌种子 -> 磁盘缓存 -> 后台刷新。"""

    def __init__(self):
        self.lock = threading.RLock()
        self.areas = []              # 有效 area id 列表
        self.types = {}              # type_id -> [cid]
        self.regions = {}            # region_id -> [cid]
        self.stations = {}           # cid -> {"n","p","c","r"}
        self.cat_titles = {}         # type_id -> 标题
        self.region_titles = {}      # region_id -> 标题
        self.built = 0               # 数据生成时间
        self.version = 0
        self.source = "none"         # seed / cache / net
        self._seed_built = 0
        self._refreshing = False
        self._search_index = None

    # ---------------- 载入 ---------------- #
    def load_seed(self):
        try:
            raw = zlib.decompress(base64.b64decode(SEED_B64))
            d = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            print("[qtfm] 内嵌种子解析失败 %s" % exc, file=sys.stderr)
            return False
        with self.lock:
            self._apply(d, "seed")
        self._seed_built = int(d.get("built") or 0)
        return True

    def load_cache(self):
        """读磁盘缓存。缓存比内嵌种子旧就弃用（种子更新）。"""
        path = _cache_path()
        if not path:
            return False
        try:
            with open(path, "r", encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            return False
        if not isinstance(d, dict):
            return False
        if d.get("version") != CACHE_VERSION:
            return False
        if not d.get("stations"):
            return False
        if int(d.get("built") or 0) < getattr(self, "_seed_built", 0):
            return False
        with self.lock:
            self._apply(d, "cache")
        return True

    def save_cache(self):
        path = _cache_path()
        if not path:
            return False
        with self.lock:
            payload = {"version": CACHE_VERSION, "built": self.built,
                       "areas": self.areas, "types": self.types,
                       "regions": self.regions, "stations": self.stations,
                       "cat_titles": self.cat_titles,
                       "region_titles": self.region_titles}
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)
            return True
        except Exception as exc:
            print("[qtfm] 写缓存失败 %s" % exc, file=sys.stderr)
            return False

    def _apply(self, d, source):
        self.areas = [int(x) for x in (d.get("areas") or [])]
        self.types = {str(k): [int(c) for c in v]
                      for k, v in (d.get("types") or {}).items()}
        self.regions = {str(k): [int(c) for c in v]
                        for k, v in (d.get("regions") or {}).items()}
        self.stations = dict(d.get("stations") or {})
        self.cat_titles = {str(k): v for k, v in (d.get("cat_titles") or {}).items()}
        self.region_titles = {str(k): v for k, v in (d.get("region_titles") or {}).items()}
        self.built = int(d.get("built") or 0)
        self.version = int(d.get("version") or 0)
        self.source = source
        self._search_index = None

    # ---------------- 查询 ---------------- #
    def fresh(self):
        if not self.built:
            return False
        age = time.time() - self.built
        return age < TTL_HOURS * 3600

    def station(self, cid):
        return self.stations.get(str(cid))

    def cids_of(self, tid):
        """分类 id -> 台 id 列表。t_ 表示类型，r_ 表示地区。"""
        with self.lock:
            key = str(tid)
            if key.startswith("t_"):
                return list(self.types.get(key[2:], []))
            if key.startswith("r_"):
                return list(self.regions.get(key[2:], []))
            return []

    def search(self, kw):
        """全量台表在内存里，搜索不需要网络。"""
        kw = (kw or "").strip().lower()
        if not kw:
            return []
        with self.lock:
            if self._search_index is None:
                idx = []
                for cid, st in self.stations.items():
                    idx.append((str(cid), st))
                self._search_index = idx
            index = self._search_index
        out = []
        for cid, st in index:
            name = st.get("n") or ""
            if kw in name.lower():
                out.append((cid, st))
        return out


DATA = _Data()


# --------------------------------------------------------------------------- #
# HTTP（只在后台线程用）
# --------------------------------------------------------------------------- #
def _http_json(url, timeout=TIMEOUT, retries=1):
    last = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=timeout) as fh:
                raw = fh.read()
            return json.loads(raw.decode("utf-8", "replace"))
        except Exception as exc:
            last = exc
            if attempt < retries:
                time.sleep(0.3)
    return None


def _rows_of(data):
    """取 radioList；接口偶尔回非列表，坏数据当空列表，别让整页崩掉。"""
    if not isinstance(data, dict):
        return []
    rows = data.get("radioList")
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _list0(area_id):
    data = _http_json("%s/radio/list/0/%s" % (WEB_API, area_id), retries=0)
    return _rows_of(data)


def _list_by(type_id, area_id):
    data = _http_json("%s/radio/list/%s/%s" % (WEB_API, type_id, area_id))
    return _rows_of(data)


def _page(fid):
    data = _http_json("%s/radiopage/list/%s" % (WEB_API, fid), retries=0)
    return _rows_of(data)


def _merge(stations, rows_):
    for it in rows_ or []:
        if not isinstance(it, dict):
            continue
        cid = it.get("content_id")
        if cid is None:
            continue
        try:
            cid = int(cid)
        except Exception:
            continue
        stations[str(cid)] = {
            "n": it.get("title") or "",
            "p": it.get("cover") or "",
            "c": [x.get("title") for x in (it.get("categories") or [])
                  if isinstance(x, dict) and x.get("title")],
            "r": (it.get("region") or {}).get("title") or "",
        }


# --------------------------------------------------------------------------- #
# 后台刷新
# --------------------------------------------------------------------------- #
def _refresh_all():
    """
    全量刷新（重活，只在后台线程跑）：
    扫 area id -> 每个类型 x 全部 area -> 每个地区 x 全部类型。
    约 4200 次请求，前台完全不参与。
    """
    t0 = time.time()
    print("[qtfm] 后台开始全量刷新", file=sys.stderr)

    fd = _http_json(WEB_API + "/radio/filter")
    regions, cats = [], []
    if isinstance(fd, dict):
        for r in (fd.get("regionsRes") or []):
            if isinstance(r, dict) and r.get("id") is not None:
                regions.append((int(r["id"]), r.get("title") or ""))
        for c in (fd.get("channelCategoriesRes") or []):
            if isinstance(c, dict) and c.get("id") is not None:
                cats.append((int(c["id"]), c.get("title") or ""))

    scan = list(range(1, MAX_AREA_ID + 1))
    alive = []
    if ThreadPoolExecutor is not None:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for aid, rr in zip(scan, pool.map(_list0, scan)):
                if rr:
                    alive.append(aid)
    else:
        for aid in scan:
            if _list0(aid):
                alive.append(aid)

    stations = {}
    types = {}
    for tid, _t in cats:
        got = {}
        if ThreadPoolExecutor is not None:
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                for rr in pool.map(lambda a: _list_by(tid, a), alive):
                    for it in rr:
                        cid = it.get("content_id")
                        if cid is not None:
                            got[int(cid)] = it
        else:
            for a in alive:
                for it in _list_by(tid, a):
                    cid = it.get("content_id")
                    if cid is not None:
                        got[int(cid)] = it
        for it in _page(tid):
            cid = it.get("content_id")
            if cid is not None:
                got[int(cid)] = it
        types[str(tid)] = sorted(got.keys())
        _merge(stations, got.values())
        print("[qtfm]   类型 %s -> %d (%.1fs)" % (_t, len(got), time.time() - t0),
              file=sys.stderr)

    regions_map = {}
    for rid, rname in regions:
        got = {}
        if ThreadPoolExecutor is not None:
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                for rr in pool.map(lambda t: _list_by(t, rid), [c[0] for c in cats]):
                    for it in rr:
                        cid = it.get("content_id")
                        if cid is not None:
                            got[int(cid)] = it
        else:
            for t in [c[0] for c in cats]:
                for it in _list_by(t, rid):
                    cid = it.get("content_id")
                    if cid is not None:
                        got[int(cid)] = it
        regions_map[str(rid)] = sorted(got.keys())
        _merge(stations, got.values())

    payload = {"version": CACHE_VERSION, "built": int(time.time()),
               "areas": alive, "types": types, "regions": regions_map,
               "stations": stations,
               "cat_titles": {str(c[0]): c[1] for c in cats},
               "region_titles": {str(r[0]): r[1] for r in regions}}
    with DATA.lock:
        DATA._apply(payload, "net")
    DATA.save_cache()
    print("[qtfm] 后台刷新完成，台数 %d，用时 %.1fs"
          % (len(stations), time.time() - t0), file=sys.stderr)


def _refresh_missing(tid):
    """增量补齐：只补一个分类，不动其它数据。"""
    key = str(tid)
    if key.startswith("t_"):
        areas = DATA.areas or []
        if not areas:
            return
        got = {}
        if ThreadPoolExecutor is not None:
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                for rr in pool.map(lambda a: _list_by(key[2:], a), areas):
                    for it in rr:
                        cid = it.get("content_id")
                        if cid is not None:
                            got[int(cid)] = it
        else:
            for a in areas:
                for it in _list_by(key[2:], a):
                    cid = it.get("content_id")
                    if cid is not None:
                        got[int(cid)] = it
        for it in _page(key[2:]):
            cid = it.get("content_id")
            if cid is not None:
                got[int(cid)] = it
        with DATA.lock:
            DATA.types[key[2:]] = sorted(got.keys())
            _merge(DATA.stations, got.values())
            DATA.built = int(time.time())
    else:
        cats = list(DATA.cat_titles.keys())
        got = {}
        if ThreadPoolExecutor is not None:
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                for rr in pool.map(lambda t: _list_by(t, key[2:]), cats):
                    for it in rr:
                        cid = it.get("content_id")
                        if cid is not None:
                            got[int(cid)] = it
        else:
            for t in cats:
                for it in _list_by(t, key[2:]):
                    cid = it.get("content_id")
                    if cid is not None:
                        got[int(cid)] = it
        with DATA.lock:
            DATA.regions[key[2:]] = sorted(got.keys())
            _merge(DATA.stations, got.values())
            DATA.built = int(time.time())
    DATA.save_cache()
    print("[qtfm] 增量补齐 %s -> %d" % (key, len(got)), file=sys.stderr)


def _start_background(fn):
    """把一个耗时函数丢到后台线程跑，前台不等。"""
    def worker():
        try:
            fn()
        except Exception as exc:
            print("[qtfm] 后台任务失败 %s" % exc, file=sys.stderr)

    try:
        th = threading.Thread(target=worker)
        th.daemon = True
        th.start()
    except Exception:
        pass


def _start_refresh(force=False):
    """启动后台刷新。已有新鲜数据就不重复干活。"""
    if force:
        pass
    elif DATA.fresh():
        return
    if DATA._refreshing:
        return
    DATA._refreshing = True

    def worker():
        try:
            _refresh_all()
        except Exception as exc:
            print("[qtfm] 后台刷新失败 %s" % exc, file=sys.stderr)
        finally:
            DATA._refreshing = False

    try:
        th = threading.Thread(target=worker)
        th.daemon = True
        th.start()
    except Exception:
        worker()


def _start_incremental(tid):
    """后台增量补某个分类。"""
    def worker():
        try:
            _refresh_missing(tid)
        except Exception as exc:
            print("[qtfm] 增量补齐失败 %s" % exc, file=sys.stderr)

    try:
        th = threading.Thread(target=worker)
        th.daemon = True
        th.start()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 播放签名
# --------------------------------------------------------------------------- #
def build_live_url(channel_id, ts, base_host=LIVE_HOST):
    path = "/live/%s/64k.mp3" % channel_id
    sign_src = "app_id=web&path=%s&ts=%s" % (quote(path, safe=""), ts)
    sign = hmac.new(SIGN_KEY, sign_src.encode("utf-8"), hashlib.md5).hexdigest()
    return "%s%s?app_id=web&ts=%s&sign=%s" % (base_host, path, ts, sign)


def make_ts(offset_hours=TS_OFFSET_HOURS):
    return format(int(time.time()) + int(offset_hours * 3600), "x")


# --------------------------------------------------------------------------- #
# Spider
# --------------------------------------------------------------------------- #
class Spider(_Base):

    siteUrl = "https://m.qtfm.cn/#/home"

    def init(self, extend=""):
        self.extend = extend or ""
        # 启动路径：先内嵌种子（零网络，毫秒可用），再磁盘缓存（可能更新），
        # 最后后台异步刷新。前台不等待任何网络。
        if not DATA.stations:
            DATA.load_seed()
        DATA.load_cache()
        # 种子落盘：让缓存目录里始终有一份可用数据（首启后即有文件可查、可删）。
        # 这里必须同步写：放后台线程的话，主线程会先 exit()，线程还没写完进程就没了。
        # 只在文件不存在时写，且实测耗时几毫秒。
        if DATA.source == "seed":
            path = _cache_path()
            if path and not os.path.exists(path):
                DATA.save_cache()
        _start_refresh()

    def getName(self):
        return "蜻蜓FM广播"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ---------------- 首页 ---------------- #
    def homeContent(self, filter):
        """只返回分类列表，绝不做网络抓取，必须毫秒级返回。"""
        result = {"class": [], "filters": {}}
        for tid, title in sorted(DATA.cat_titles.items(), key=lambda kv: int(kv[0])):
            result["class"].append({"type_id": "t_%s" % tid, "type_name": title})
        for rid, title in sorted(DATA.region_titles.items(), key=lambda kv: int(kv[0])):
            result["class"].append({"type_id": "r_%s" % rid, "type_name": title})
        if not result["class"]:
            # 极端情况：种子和缓存都不可用，用内置兜底表保证首页不为空
            for tid, title in _FALLBACK_TYPES:
                result["class"].append({"type_id": "t_%d" % tid, "type_name": title})
            for rid, title in _FALLBACK_REGIONS:
                result["class"].append({"type_id": "r_%d" % rid, "type_name": title})
        return result

    # ---------------- 分类页 ---------------- #
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        tid = str(tid or "")
        cids = DATA.cids_of(tid)
        if not cids:
            # 缺这个分类：后台补，前台先给空列表（不阻塞）
            _start_incremental(tid)
            return {"list": [], "page": page, "pagecount": 1, "limit": 60, "total": 0}
        items = []
        for cid in cids:
            st = DATA.station(cid)
            if not st:
                continue
            name = st.get("n") or ("电台%s" % cid)
            cats = st.get("c") or []
            remark = "/".join(cats) or st.get("r") or "广播"
            items.append({"cid": cid, "name": name, "pic": st.get("p") or "",
                          "remark": remark})
        items.sort(key=lambda x: x["name"])
        per = 60
        total = len(items)
        pagecount = max(1, (total + per - 1) // per)
        page = min(page, pagecount)
        out = []
        for it in items[(page - 1) * per: page * per]:
            out.append({"vod_id": "qtfm_%s" % it["cid"],
                        "vod_name": it["name"],
                        "vod_pic": it["pic"],
                        "vod_remarks": it["remark"]})
        return {"list": out, "page": page, "pagecount": pagecount,
                "limit": per, "total": total}

    # ---------------- 详情 ---------------- #
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        token = str(ids[0]) if ids else ""
        if not token.startswith("qtfm_"):
            return {"list": []}
        cid = token[5:]
        st = DATA.station(cid)
        name = (st.get("n") if st else None) or ("电台%s" % cid)
        remark = "/".join((st.get("c") or [])) if st else ""
        return {"list": [{
            "vod_id": token,
            "vod_name": name,
            "vod_remarks": remark or "广播",
            "type_name": "蜻蜓FM",
            "vod_content": "蜻蜓FM 广播电台：%s" % name,
            "vod_play_from": "直播",
            "vod_play_url": "直播$%s" % token,
        }]}

    # ---------------- 播放 ---------------- #
    def playerContent(self, flag, id, vipFlags):
        """纯本地算签名，零网络零等待。"""
        token = str(id or "")
        if not token.startswith("qtfm_"):
            return {"parse": 0, "url": ""}
        cid = token[5:]
        url = build_live_url(cid, make_ts())
        return {"parse": 0, "url": url,
                "header": {"User-Agent": UA, "Referer": "https://m.qtfm.cn/"}}

    # ---------------- 搜索 ---------------- #
    def searchContent(self, key, quick=False, pg=1):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        hits = DATA.search(key)
        out = []
        for cid, st in hits:
            name = st.get("n") or ""
            cats = st.get("c") or []
            out.append({"vod_id": "qtfm_%s" % cid, "vod_name": name,
                        "vod_pic": st.get("p") or "",
                        "vod_remarks": "/".join(cats) or st.get("r") or "广播"})
        out.sort(key=lambda x: x["vod_name"])
        per = 20
        pagecount = max(1, (len(out) + per - 1) // per)
        page = min(page, pagecount)
        return {"list": out[(page - 1) * per: page * per], "page": page,
                "pagecount": pagecount, "limit": per, "total": len(out)}


# 兜底分类表：种子/缓存都读不到时，首页也不至于空白
_FALLBACK_TYPES = [(433, "资讯台"), (442, "音乐台"), (429, "交通台"),
                   (439, "经济台"), (432, "文艺台"), (441, "都市台"),
                   (430, "体育台"), (431, "双语台"), (440, "综合台"),
                   (438, "生活台"), (435, "旅游台"), (436, "曲艺台"),
                   (434, "方言台")]
_FALLBACK_REGIONS = [(407, "网络台"), (3, "北京"), (5, "天津"), (7, "河北"),
                     (83, "上海"), (19, "山西"), (45, "内蒙古"), (21, "辽宁"),
                     (61, "吉林"), (77, "黑龙江"), (85, "江苏"), (99, "浙江"),
                     (111, "安徽"), (129, "福建"), (139, "江西"), (151, "山东"),
                     (169, "河南"), (187, "湖北"), (202, "湖南"), (217, "广东"),
                     (239, "广西"), (254, "海南"), (257, "重庆"), (259, "四川"),
                     (281, "贵州"), (291, "云南"), (316, "陕西"), (327, "甘肃"),
                     (351, "宁夏"), (357, "新疆"), (308, "西藏"), (342, "青海")]


# --------------------------------------------------------------------------- #
# 本地自测
# --------------------------------------------------------------------------- #
def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="蜻蜓FM 广播 TVBox Spider 自测")
    ap.add_argument("--bench", action="store_true", help="跑各方法耗时基准")
    ap.add_argument("--categories", action="store_true", help="只打印站点分类体系")
    ap.add_argument("--probe", type=int, default=0, help="抽样探测多少条直播地址")
    ap.add_argument("--category", default="", help="指定分类 id，如 t_440 / r_7")
    ap.add_argument("--all-types", action="store_true", help="统计全部 13 个类型分类的条数")
    ap.add_argument("--refresh", action="store_true", help="强制跑一次后台全量刷新")
    ap.add_argument("--no-proxy", action="store_true",
                    help="探测直播地址时忽略环境里的 HTTP 代理（代理会拦媒体流）")
    args = ap.parse_args()

    s = Spider()
    t0 = time.time()
    s.init("")
    print("init 用时 %.1f ms（数据源: %s）" % ((time.time() - t0) * 1000, DATA.source))
    print("缓存目录: %s" % (_cache_path() or "不可写，暂用内嵌种子"))

    def timed(label, fn):
        t = time.time()
        r = fn()
        print("  %-28s %8.1f ms" % (label, (time.time() - t) * 1000))
        return r

    if args.bench:
        print("\n== 计时（前台调用，含返回数据） ==")
        h = timed("homeContent 首", lambda: s.homeContent(True))
        timed("homeContent 二", lambda: s.homeContent(True))
        c = timed("categoryContent t_440 首", lambda: s.categoryContent("t_440", 1, False, {}))
        print("      -> total=%d" % c.get("total"))
        timed("categoryContent t_440 二", lambda: s.categoryContent("t_440", 1, False, {}))
        timed("categoryContent r_7 首", lambda: s.categoryContent("r_7", 1, False, {}))
        timed("detailContent", lambda: s.detailContent(["qtfm_1153"]))
        timed("playerContent", lambda: s.playerContent("", "qtfm_1153", []))
        sr = timed("searchContent 首", lambda: s.searchContent("交通", False, 1))
        print("      -> total=%d" % sr.get("total"))
        timed("searchContent 二", lambda: s.searchContent("交通", False, 1))
        return 0

    if args.refresh:
        _refresh_all()
        return 0

    print("分类体系: %d 个一级分类" % len(s.homeContent(True)["class"]))
    for it in s.homeContent(True)["class"][:5]:
        print("   %-6s %s" % (it["type_id"], it["type_name"]))
    if args.categories:
        return 0

    if args.all_types:
        total = 0
        for tid, title in sorted(DATA.cat_titles.items(), key=lambda kv: int(kv[0])):
            n = len(DATA.cids_of("t_%s" % tid))
            total += n
            print("  %-6s %-6s -> %4d 个" % (tid, title, n))
        print("类型维度合计 %d，去重台数 %d" % (total, len(DATA.stations)))
        return 0

    tid = args.category or ("t_440" if "440" in DATA.cat_titles else "")
    cat = s.categoryContent(tid, 1, False, {})
    print("\n分类 %s -> %d 条" % (tid, cat.get("total")))
    for it in (cat.get("list") or [])[:5]:
        print("   %-28s %s" % (it["vod_name"][:28], it["vod_remarks"]))
    if cat.get("list"):
        det = s.detailContent([cat["list"][0]["vod_id"]])
        print("detail:", json.dumps(det, ensure_ascii=False)[:240])
        play = s.playerContent("", cat["list"][0]["vod_id"], [])
        print("play:", json.dumps(play, ensure_ascii=False)[:240])

    if args.probe:
        print("\n抽样探测直播地址 ...")
        ok = 0
        picked = (cat.get("list") or [])[:args.probe]
        opener = build_opener(ProxyHandler({})) if args.no_proxy else build_opener()
        for it in picked:
            url = s.playerContent("", it["vod_id"], [])["url"]
            try:
                req = Request(url, headers=HEADERS)
                with opener.open(req, timeout=10) as fh:
                    chunk = fh.read(2048)
                    ct = fh.headers.get("Content-Type") or ""
                    code = fh.getcode()
                good = code == 200 and bool(chunk)
                ok += 1 if good else 0
                print("  %-24s -> %s %s %dB %s" % (it["vod_name"][:24], code, ct,
                                                   len(chunk), "可播" if good else "异常"))
            except Exception as exc:
                print("  %-24s -> 探测失败 %s" % (it["vod_name"][:24], type(exc).__name__))
        print("探测结果 %d/%d 可播" % (ok, len(picked)))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
