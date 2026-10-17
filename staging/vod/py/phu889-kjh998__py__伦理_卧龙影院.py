# -*- coding: utf-8 -*-
# 卧龙影院 https://xrpo.eu.cc/ TVBox 蜘蛛
# 按 ~/workspace/user/files/TVBox_spider.py 模板契约
import re, json, base64
try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:
    def __init__(self):
        self.site = "https://xrpo.eu.cc"
        self.name = "卧龙影院"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        # 6 大类
        self.CATS = [
            {"id": "1", "name": "电影"},
            {"id": "2", "name": "连续剧"},
            {"id": "3", "name": "综艺"},
            {"id": "4", "name": "动漫"},
            {"id": "35", "name": "体育赛事"},
            {"id": "56", "name": "论理片"},
        ]
        # 二级分类：类型(段2) / 地区(段0) / 年份(段10) / 语言(段3)
        _types = {
            "1": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪", "动画", "奇幻", "武侠", "冒险", "悬疑", "惊悚"],
            "2": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "爱情", "科幻"],
            "3": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实"],
            "4": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园"],
            "35": ["足球", "篮球", "网球", "斯诺克"],
            "56": ["伦理", "写真"],
        }
        _areas = ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国", "泰国", "印度", "其他"]
        _years = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018"]
        _langs = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语"]
        self.FILTERS = {}
        for c in self.CATS:
            cid = c["id"]
            flts = []
            if _types.get(cid):
                flts.append({"key": "class", "name": "类型",
                             "value": [{"n": "全部", "v": ""}] + [{"n": t, "v": t} for t in _types[cid]]})
            flts.append({"key": "area", "name": "地区",
                         "value": [{"n": "全部", "v": ""}] + [{"n": a, "v": a} for a in _areas]})
            flts.append({"key": "year", "name": "年份",
                         "value": [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in _years]})
            if cid in ("1", "2"):
                flts.append({"key": "lang", "name": "语言",
                             "value": [{"n": "全部", "v": ""}] + [{"n": l, "v": l} for l in _langs]})
            self.FILTERS[cid] = flts

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).lower()
        return u.endswith((".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi")) or "m3u8" in u

    def destroy(self):
        pass

    def action(self, action):
        return {}

    def _get(self, url, referer=None):
        h = dict(self.header)
        if referer:
            h["Referer"] = referer
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=12, allow_redirects=True)
                if r.status_code < 400:
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _u(self, u):
        if not u:
            return u
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            m = re.match(r"(https?://[^/]+)", self.site)
            return (m.group(1) if m else self.site) + u
        return self.site.rstrip("/") + "/" + u.lstrip("/")

    def _clean(self, s):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

    def _items(self, html, limit=36):
        out = []
        seen = set()
        # 卡片: /xq/{id}.html，封面在 a[data-original] 或内部 img
        for m in re.finditer(r'<a\b[^>]*?href="(/xq/(\d+)\.html)"[^>]*>([\s\S]*?)</a>', html, re.I):
            vid = m.group(2)
            if vid in seen:
                continue
            inner = m.group(3)
            tag = m.group(0)[:m.group(0).index(">") + 1]
            nm = ""
            tm = re.search(r'title="([^"]*)"', tag)
            if tm:
                nm = tm.group(1)
            if not nm:
                tm2 = re.search(r'title="([^"]*)"', inner)
                if tm2:
                    nm = tm2.group(1)
            nm = self._clean(nm)
            if not nm:
                continue
            pic = ""
            pm = re.search(r'data-original="([^"]+)"', tag)
            if not pm:
                pm = re.search(r'<img[^>]*data-src="([^"]+)"|<img[^>]*data-original="([^"]+)"|<img[^>]*src="(https?://[^"\s]+)"', inner, re.I)
                if pm:
                    pic = self._u(pm.group(1) or pm.group(2) or pm.group(3))
            else:
                pic = self._u(pm.group(1))
            if not pic:
                continue
            rk = ""
            rm = re.search(r'class="[^"]*pic-text[^"]*"[^>]*>([^<]*)<', tag + inner)
            if rm:
                rk = self._clean(rm.group(1))
            seen.add(vid)
            out.append({
                "vod_id": vid,
                "vod_name": nm[:80],
                "vod_pic": pic,
                "vod_remarks": rk,
            })
            if len(out) >= limit:
                break
        return out

    def _pagecount(self, html, pg):
        m = re.search(r">(\d+)/(\d+)<", html)
        if m:
            return max(int(m.group(2)), pg)
        return pg

    def init(self, extend=""):
        pass

    def homeContent(self, filter=None):
        html = self._get(self.site + "/")
        cats = [{"type_id": c["id"], "type_name": c["name"]} for c in self.CATS]
        return {"class": cats, "filters": self.FILTERS, "list": self._items(html, 60)}

    def homeVideoContent(self):
        return {"list": self._items(self._get(self.site + "/"), 60)}

    def _cat_url(self, tid, pg, extend):
        # /vodshow/{id}-{area}-{order}-{class}-{lang}-{letter}----{page}---{year}.html
        area = cl = year = lang = ""
        if isinstance(extend, dict):
            area = str(extend.get("area") or "")
            cl = str(extend.get("class") or "")
            year = str(extend.get("year") or "")
            lang = str(extend.get("lang") or "")
        elif isinstance(extend, str) and extend.strip():
            try:
                e = json.loads(extend)
                area = str(e.get("area") or "")
                cl = str(e.get("class") or "")
                year = str(e.get("year") or "")
                lang = str(e.get("lang") or "")
            except Exception:
                pass
        from urllib.parse import quote
        segs = [""] * 11
        segs[0] = quote(area, safe="") if area else ""
        segs[2] = quote(cl, safe="") if cl else ""
        segs[3] = quote(lang, safe="") if lang else ""
        segs[7] = str(pg)
        segs[10] = year
        return "%s/vodshow/%s-%s.html" % (self.site, tid, "-".join(segs))

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        url = self._cat_url(str(tid), pg, extend)
        html = self._get(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 36, "total": 0}
        vod_list = self._items(html, 36)
        pagecount = self._pagecount(html, pg)
        return {"list": vod_list, "page": pg, "pagecount": pagecount,
                "limit": 36, "total": pagecount * 36}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids or "")
        vid = re.search(r"(\d+)", str(vid))
        vid = vid.group(1) if vid else ""
        if not vid:
            return {"list": []}
        html = self._get("%s/xq/%s.html" % (self.site, vid))
        if not html:
            return {"list": []}
        title = ""
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        if tm:
            title = self._clean(re.sub(r"<span[^>]*>.*?</span>", "", tm.group(1), flags=re.S))
        if not title:
            tm = re.search(r"<title>(.*?)</title>", html, re.S)
            if tm:
                title = self._clean(tm.group(1)).split("-")[0].strip("《》 ")
        pic = ""
        im = re.search(r'property="og:image" content="([^"]+)"', html)
        if im:
            pic = self._u(im.group(1))
        desc = ""
        dm = re.search(r'property="og:description" content="([^"]+)"', html)
        if dm:
            desc = self._clean(dm.group(1))[:800]
        # 线路/选集: /bf/{vid}-{sid}-{nid}.html
        lines = {}
        for m in re.finditer(r'href="(/bf/%s-(\d+)-(\d+)\.html)"[^>]*>([^<]*)</a>' % vid, html):
            sid, nid, name = m.group(2), m.group(3), self._clean(m.group(4))
            if not name or name == "立即播放":
                name = "第%s集" % nid
            lines.setdefault(sid, []).append((int(nid), name, m.group(1)))
        play_from = []
        play_url = []
        for sid in sorted(lines.keys(), key=int):
            eps = sorted(lines[sid])
            play_from.append("线路%s" % sid)
            play_url.append("#".join("%s$%s" % (n, self._u(u)) for _, n, u in eps))
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def searchContent(self, key, quick=False, pg="1"):
        from urllib.parse import quote
        url = "%s/vodsearch/%s-------------.html" % (self.site, quote(str(key or "")))
        html = self._get(url)
        if not html:
            return {"list": []}
        return {"list": self._items(html, 36)}

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids or "")
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if "$" in url:
            url = url.split("$", 1)[1]
        if not url.startswith("http"):
            url = self._u(url)
        u = url.lower()
        if u.endswith((".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi")) or "m3u8" in u:
            return {"parse": 0, "url": url, "header": dict(self.header)}
        html = self._get(url, referer=self.site + "/")
        if not html:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        # player_aaaa JSON
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})</script>', html, re.S)
        found = ""
        if m:
            try:
                j = json.loads(m.group(1))
                found = j.get("url") or ""
            except Exception:
                mm = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
                if mm:
                    found = mm.group(1).replace("\\/", "/")
        if not found:
            m2 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m2:
                found = m2.group(1)
        found = (found or "").strip().replace("\\/", "/")
        if not found:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if found.startswith("//"):
            found = "https:" + found
        elif not found.startswith("http"):
            found = self._u(found)
        return {"parse": 0, "url": found, "header": dict(self.header)}

    def localProxy(self, param):
        return [403, "text/plain", b"", None]


def _html_unescape(s):
    import html as _h
    return _h.unescape(s) if s else s
