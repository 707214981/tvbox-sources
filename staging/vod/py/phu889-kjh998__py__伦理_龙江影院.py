import re, json, base64
try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:
    def __init__(self):
        self.site = "https://ljvod.com"
        self.name = "龙江影院"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._extend = {}
        # ---- 站点分类（2026-10-16 按官网导航核对）----
        # 一级: /type-{id}/；二级分类=类型筛选；翻页 /type-{id}-{n}/
        self.CATS = [
            {"id": "1", "name": "电影", "subs": [
                ("5", "动作片"), ("6", "喜剧片"), ("7", "爱情片"),
                ("8", "科幻片"), ("9", "恐怖片"), ("10", "剧情片"),
                ("11", "战争片"), ("22", "纪录片"), ("33", "动画片")]},
            {"id": "2", "name": "连续剧", "subs": [
                ("12", "国产剧"), ("13", "香港剧"), ("14", "台湾剧"),
                ("15", "日本剧"), ("16", "韩国剧"), ("17", "欧美剧"),
                ("18", "海外剧"), ("19", "泰国剧")]},
            {"id": "3", "name": "综艺", "subs": [
                ("23", "内地综艺"), ("24", "港台综艺"),
                ("25", "日韩综艺"), ("26", "欧美综艺")]},
            {"id": "4", "name": "动漫", "subs": [
                ("28", "国产动漫"), ("29", "港台动漫"),
                ("30", "日韩动漫"), ("31", "欧美动漫"), ("32", "海外动漫")]},
            {"id": "27", "name": "短剧", "subs": []},
            {"id": "20", "name": "理论片", "subs": []},
        ]

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

    @staticmethod
    def _strip(s):
        s = re.sub(r"<[^>]+>", "", str(s or ""))
        s = s.replace("&nbsp;", " ").replace("&amp;", "&")
        return re.sub(r"\s+", " ", s).strip()

    @staticmethod
    def _clean_name(s):
        return re.sub(r"\s*[（(]\s*\d{4}\s*[）)]\s*$", "", Spider._strip(s))

    def _items(self, html, limit=36):
        out, seen = [], set()
        for m in re.finditer(r'<a[^>]*href="/show-([^/"]+)/"[^>]*>([\s\S]*?)</a>', html or "", re.I):
            vid, inner, tag = m.group(1), m.group(2), m.group(0)
            if vid in seen:
                continue
            t = re.search(r'title="([^"]*)"', tag)
            title = t.group(1) if t else ""
            if not title:
                h = re.search(r"<h4[^>]*>([\s\S]*?)</h4>", inner, re.I)
                title = h.group(1) if h else ""
            title = self._clean_name(title)
            if not title:
                continue
            pic = ""
            p = re.search(r'data-original="([^"]+)"', tag) or re.search(r'data-src="([^"]+)"', tag)
            if p:
                pic = p.group(1)
            if not pic:
                im = re.search(r'<img[^>]*src="([^"]+)"', inner, re.I)
                if im:
                    pic = im.group(1)
            if not pic or pic.startswith("data:"):
                continue
            seen.add(vid)
            rk = ""
            tm = re.search(r'<span class="time">([^<]*)</span>', inner, re.I)
            if tm:
                rk = self._strip(tm.group(1))
            out.append({
                "vod_id": self._u("/show-%s/" % vid),
                "vod_name": title,
                "vod_pic": self._u(pic),
                "vod_remarks": rk,
            })
            if len(out) >= limit:
                break
        return out

    def _pagecount(self, html, pg):
        m = re.search(r'href="/type-\d+?-(\d+)/"[^>]*title="尾页"', html or "")
        if m:
            return max(int(m.group(1)), pg)
        m2 = re.search(r">(\d+)/(\d+)<", html or "")
        if m2:
            return max(int(m2.group(2)), pg)
        return pg

    def init(self, extend=""):
        self._extend = {}
        if isinstance(extend, dict):
            self._extend = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                e = json.loads(extend)
                if isinstance(e, dict):
                    self._extend = e
            except Exception:
                pass

    def homeContent(self, filter=None):
        html = self._get(self.site)
        cats = [{"type_id": c["id"], "type_name": c["name"]} for c in self.CATS]
        filters = {}
        for c in self.CATS:
            if c["subs"]:
                filters[c["id"]] = [{
                    "key": "type", "name": "类型",
                    "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": i} for i, n in c["subs"]],
                }]
        return {"class": cats, "filters": filters, "list": self._items(html, 60)}

    def homeVideoContent(self):
        return {"list": self._items(self._get(self.site), 60)}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        sub = ""
        if isinstance(extend, dict):
            sub = str(extend.get("type") or "").strip()
        elif isinstance(extend, str) and extend.strip():
            try:
                sub = str(json.loads(extend).get("type") or "").strip()
            except Exception:
                pass
        type_id = sub or str(tid)
        if pg == 1:
            url = "%s/type-%s/" % (self.site, type_id)
        else:
            url = "%s/type-%s-%d/" % (self.site, type_id, pg)
        html = self._get(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 36, "total": 0}
        vod_list = self._items(html, 36)
        pagecount = self._pagecount(html, pg)
        return {"list": vod_list, "page": pg, "pagecount": pagecount,
                "limit": 36, "total": pagecount * 36}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = str(vid or "").strip()
        if not vid:
            return {"list": []}
        if vid.startswith("http"):
            url = vid
        elif vid.startswith("/"):
            url = self._u(vid)
        elif re.match(r"^[A-Za-z0-9]+$", vid):
            url = "%s/show-%s/" % (self.site, vid)
        else:
            url = self._u(vid)
        html = self._get(url)
        if not html:
            return {"list": []}
        # 标题
        title, type_name = "", ""
        h1 = re.search(r'<h1[^>]*class="title[^"]*"[^>]*>([\s\S]*?)</h1>', html, re.I)
        if h1:
            labs = re.findall(r'<a[^>]*class="label[^"]*"[^>]*>([^<]*)</a>', h1.group(1))
            type_name = "/".join([self._strip(x) for x in labs if self._strip(x)])
            sp = re.search(r'<span[^>]*class="font20"[^>]*>([\s\S]*?)</span>', h1.group(1), re.I)
            title = self._clean_name(sp.group(1) if sp else h1.group(1))
        if not title:
            t = re.search(r"<title>([^<]*)</title>", html, re.I)
            title = self._strip(t.group(1)).split("-")[0] if t else vid
        # 海报
        pic = ""
        di = html.find("vod-desc")
        if di >= 0:
            pm = re.search(r'data-original="([^"]+)"', html[di:di + 6000])
            if pm:
                pic = self._u(pm.group(1))
        # 元信息
        meta = {}
        key_map = {"导演": "vod_director", "主演": "vod_actor", "类型": "type_name",
                   "语言": "vod_lang", "地区": "vod_area", "年份": "vod_year"}
        seg = html[di:di + 8000] if di >= 0 else html
        for li in re.finditer(r"<li[^>]*>([\s\S]*?)</li>", seg, re.I):
            t = self._strip(li.group(1))
            for k, fk in key_map.items():
                if (t.startswith(k + "：") or t.startswith(k + ":")) and fk not in meta:
                    v = t[len(k) + 1:].strip()
                    if v and v != "未知":
                        meta[fk] = v
        # 简介
        intro = ""
        im = re.search(r'<div class="intro"[^>]*>([\s\S]*?)</div>', html, re.I)
        if im:
            intro = self._strip(im.group(1)).replace("展开", "").strip()
        # 线路与选集
        play_from, play_url = [], []
        for box in html.split("wi-play-list-box")[1:]:
            hn = re.search(r'<h2 class="title">([^<]*)</h2>', box, re.I)
            line = self._strip(hn.group(1)) if hn else "线路"
            if re.search(r"剧情介绍|热播推荐|猜你喜欢", line):
                continue
            eps, seen = [], set()
            for em in re.finditer(
                    r'<a[^>]*class="[^"]*wi-play-list-btn[^"]*"[^>]*href="(/play-[^"]+/)"[^>]*>([\s\S]*?)</a>',
                    box, re.I):
                pu, en = em.group(1), self._strip(em.group(2)) or "播放"
                if pu in seen:
                    continue
                seen.add(pu)
                eps.append("%s$%s" % (en, self._u(pu)))
            if eps:
                play_from.append(line)
                play_url.append("#".join(eps))
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": meta.get("type_name", type_name),
            "vod_content": intro,
            "vod_play_from": "$$$".join(play_from) if play_from else "默认",
            "vod_play_url": "$$$".join(play_url),
        }
        vod.update({k: v for k, v in meta.items() if k.startswith("vod_")})
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        try:
            from urllib.parse import quote
            q = quote(kw)
        except Exception:
            q = kw
        try:
            p = max(1, int(pg))
        except Exception:
            p = 1
        url = "%s/search-%s%s-------------/" % (self.site, q, ("-%d" % p) if p > 1 else "")
        html = self._get(url, referer=self.site)
        if not html:
            return {"list": []}
        m = re.search(r"<title>([^<]*)</title>", html, re.I)
        if not m or "搜索结果" not in m.group(1):
            return {"list": []}
        vod_list = self._items(html, 36)
        return {"list": vod_list}

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if not url.startswith("http"):
            url = self._u(url)
        u = url.lower()
        if u.endswith((".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi")) or "m3u8" in u:
            return {"parse": 0, "url": url, "header": dict(self.header)}
        html = self._get(url, referer=self.site)
        found = ""
        m = re.search(r"var\s+player_\w+\s*=\s*(\{.*?\})\s*[;<]", html or "", re.S)
        if m:
            try:
                d = json.loads(m.group(1))
                found = str(d.get("url") or "").replace("\\/", "/").strip()
            except Exception:
                pass
        if not found:
            m2 = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html or "")
            if m2:
                found = m2.group(1).replace("\\/", "/")
        if not found:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        return {"parse": 0, "url": self._u(found), "header": dict(self.header)}

    def localProxy(self, param):
        u = param.get("url", "") if isinstance(param, dict) else ""
        if not u:
            return [403, "text/plain", b"", None]
        h = dict(self.header)
        if self.s is not None:
            try:
                r = self.s.get(u, headers=h, timeout=15)
                return [200, r.headers.get("Content-Type", "application/octet-stream"), r.content, None]
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(u, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return [200, resp.headers.get("Content-Type", "application/octet-stream"), resp.read(), None]
        except Exception:
            return [403, "text/plain", b"", None]
