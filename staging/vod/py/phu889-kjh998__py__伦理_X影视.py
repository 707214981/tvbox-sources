import re, json
try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:
    def __init__(self):
        self.site = "https://xmovie.suyingok.com"
        self.api = "https://xmov.xsocdn.com"
        self.name = "X影视"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._extend = {}
        self._meta = None
        self._home_items = None

    def getName(self):
        return self.name

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

    def _get(self, url, referer=None):
        h = dict(self.header)
        if referer:
            h["Referer"] = referer
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=15, allow_redirects=True)
                if r.status_code < 400:
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _json(self, url):
        try:
            d = json.loads(self._get(url))
            return d if isinstance(d, dict) else None
        except Exception:
            return None

    def _u(self, u):
        if not u:
            return u
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            m = re.match(r"(https?://[^/]+)", self.api)
            return (m.group(1) if m else self.api) + u
        return self.api.rstrip("/") + "/" + u.lstrip("/")

    def _enc(self, v):
        from urllib.parse import quote
        v = (v or "").strip()
        if not v:
            return "~"
        return "v" + quote(v, safe="")

    def _meta_data(self):
        if self._meta is not None:
            return self._meta
        d = self._json(self.api + "/data/1/meta.json")
        cats = []
        if d:
            for c in d.get("categories") or []:
                slug = str(c.get("slug") or "").strip()
                name = str(c.get("name") or "").strip()
                if slug and name:
                    cats.append({
                        "slug": slug,
                        "name": name,
                        "genres": [str(x) for x in c.get("genres") or []],
                        "regions": [str(x) for x in c.get("regions") or []],
                        "years": [str(x) for x in c.get("years") or []],
                        "forms": [str(x) for x in c.get("forms") or []],
                    })
        if not cats:
            cats = [
                {"slug": "movie", "name": "电影", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "tv", "name": "电视剧", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "variety", "name": "综艺", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "animation", "name": "动漫", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "short", "name": "短剧", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "documentary", "name": "纪录片", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "sport", "name": "体育", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "trailer", "name": "预告片", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "commentary", "name": "影视解说", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "ethics", "name": "伦理", "genres": [], "regions": [], "years": [], "forms": []},
                {"slug": "science", "name": "科普", "genres": [], "regions": [], "years": [], "forms": []},
            ]
        self._meta = cats
        return cats

    def _hot_slugs(self):
        return {"movie", "tv", "variety", "animation", "documentary"}

    def _default_sort(self, slug):
        return "hot" if slug in self._hot_slugs() else "latest"

    def _filters(self):
        out = {}
        for c in self._meta_data():
            slug = c["slug"]
            fl = []
            if slug in self._hot_slugs():
                sort_vals = [{"n": "热门", "v": "hot"}, {"n": "最新", "v": "latest"}, {"n": "年份最新", "v": "year"}]
            else:
                sort_vals = [{"n": "最新", "v": "latest"}, {"n": "年份最新", "v": "year"}]
            fl.append({"key": "sort", "name": "排序", "value": sort_vals})
            if c["genres"]:
                gname = "项目" if slug == "sport" else "题材"
                fl.append({"key": "genre", "name": gname, "value": [{"n": "全部", "v": ""}] + [{"n": g, "v": g} for g in c["genres"]]})
            if c["regions"]:
                fl.append({"key": "region", "name": "地区", "value": [{"n": "全部", "v": ""}] + [{"n": g, "v": g} for g in c["regions"]]})
            if c["years"]:
                fl.append({"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": g, "v": g} for g in c["years"]]})
            if c["forms"]:
                fname = "联赛" if slug == "sport" else "形态"
                fl.append({"key": "form", "name": fname, "value": [{"n": "全部", "v": ""}] + [{"n": g, "v": g} for g in c["forms"]]})
            out[slug] = fl
        return out

    def _clean_region(self, v):
        return " ".join(str(v or "").split())

    def _item(self, it):
        try:
            if not isinstance(it, dict):
                return None
            if it.get("external"):
                return None
            if not it.get("playable"):
                return None
            vid = str(it.get("id") or "").strip()
            if not vid or not vid.isdigit():
                return None
            title = str(it.get("title") or "").strip()
            if not title:
                return None
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._u(it.get("poster") or ""),
                "vod_remarks": str(it.get("progress") or ""),
                "vod_year": str(it.get("year") or ""),
                "vod_area": self._clean_region(it.get("region") or ""),
            }
            directors = str(it.get("directors") or "").strip()
            if directors:
                vod["vod_director"] = directors
            actors = str(it.get("actors") or "").strip()
            if actors:
                vod["vod_actor"] = actors
            return vod
        except Exception:
            return None

    def _items(self, data):
        out = []
        seen = set()
        if not data:
            return out
        for it in data.get("items") or []:
            vod = self._item(it)
            if vod and vod["vod_id"] not in seen:
                seen.add(vod["vod_id"])
                out.append(vod)
        return out

    def _home_list(self):
        if self._home_items is not None:
            return self._home_items
        out = []
        seen = set()
        d = self._json(self.api + "/data/1/home.json")
        if d:
            for sec in d.get("sections") or []:
                for it in sec.get("items") or []:
                    vod = self._item(it)
                    if vod and vod["vod_id"] not in seen:
                        seen.add(vod["vod_id"])
                        out.append(vod)
        if not out:
            cats = self._meta_data()
            if cats:
                slug = cats[0]["slug"]
                url = self.api + "/data/1/list/" + slug + "/hot/1/~/~/~/~.json"
                out = self._items(self._json(url))
        self._home_items = out
        return out

    def homeContent(self, filter=None):
        cats = self._meta_data()
        classes = [{"type_id": c["slug"], "type_name": c["name"]} for c in cats]
        return {"class": classes, "filters": self._filters(), "list": self._home_list()}

    def homeVideoContent(self):
        return {"list": self._home_list()}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        slug = str(tid or "").strip()
        ext = extend if isinstance(extend, dict) else {}
        sort = str(ext.get("sort") or "").strip()
        if slug in self._hot_slugs():
            if sort not in ("hot", "latest", "year"):
                sort = "hot"
        else:
            if sort not in ("latest", "year"):
                sort = "latest"
        url = "/".join([
            self.api + "/data/1/list",
            slug,
            sort,
            str(pg),
            self._enc(ext.get("genre")),
            self._enc(ext.get("region")),
            self._enc(ext.get("year")),
            self._enc(ext.get("form")),
        ]) + ".json"
        d = self._json(url)
        if not d:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        try:
            pagecount = int(d.get("pages") or 1)
        except Exception:
            pagecount = 1
        try:
            total = int(d.get("total") or 0)
        except Exception:
            total = 0
        return {"list": self._items(d), "page": pg, "pagecount": pagecount, "limit": 24, "total": total}

    def detailContent(self, ids):
        vid = ids
        if isinstance(ids, (list, tuple)):
            vid = ids[0] if ids else ""
        vid = str(vid or "").strip()
        if not vid or not vid.isdigit():
            return {"list": []}
        d = self._json(self.api + "/data/1/work/" + vid + ".json")
        if not d:
            return {"list": []}
        lines = d.get("lines") or []
        play_from = []
        play_url = []
        for line in lines:
            try:
                lid = str(line.get("id") or "").strip()
                lname = str(line.get("name") or "").strip() or ("线路" + lid)
                if not lid:
                    continue
                try:
                    count = int(line.get("count") or 0)
                except Exception:
                    count = 0
                if count < 1:
                    count = 1
                if count == 1:
                    labels = ["正片"]
                else:
                    labels = ["第%d集" % i for i in range(1, count + 1)]
                eps = []
                for i, label in enumerate(labels, 1):
                    eps.append("%s$%s@%s@%d" % (label, vid, lid, i))
                play_from.append(lname)
                play_url.append("#".join(eps))
            except Exception:
                continue
        summary = str(d.get("summary") or "").strip()
        vod = {
            "vod_id": vid,
            "vod_name": str(d.get("title") or ""),
            "vod_pic": self._u(d.get("poster") or ""),
            "vod_year": str(d.get("year") or ""),
            "vod_area": self._clean_region(d.get("region") or ""),
            "vod_director": str(d.get("directors") or ""),
            "vod_actor": str(d.get("actors") or ""),
            "vod_content": summary,
            "vod_remarks": str(d.get("progress") or ""),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        url = "/".join([
            self.api + "/data/1/search",
            "all",
            "relevance",
            str(pg),
            self._enc(key),
            "~",
            "~",
            "~",
            "~",
        ]) + ".json"
        d = self._json(url)
        if not d:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        try:
            pagecount = int(d.get("pages") or 1)
        except Exception:
            pagecount = 1
        try:
            total = int(d.get("total") or 0)
        except Exception:
            total = 0
        return {"list": self._items(d), "page": pg, "pagecount": pagecount, "limit": 24, "total": total}

    def _resolve_playlist(self, line):
        if not isinstance(line, dict):
            return []
        data = None
        for key in ("playlist", "playlist_v3"):
            u = line.get(key) or ""
            if not u:
                continue
            d = self._json(u)
            if d and (d.get("items") or []):
                data = d
                break
        if not data:
            return []
        items = data.get("items") or []
        origins = data.get("origins") or {}
        if not origins:
            dm = self._json(self.api + "/domain-map/1/current.json")
            if dm:
                origins = dm.get("origins") or {}
        out = []
        for it in items:
            try:
                if not isinstance(it, dict):
                    continue
                u = it.get("url") or ""
                if not u:
                    oid = it.get("origin_id")
                    base = ""
                    if oid is not None:
                        base = origins.get(str(oid)) or origins.get(oid) or ""
                    suffix = it.get("suffix") or ""
                    if base and suffix:
                        u = base.rstrip("/") + suffix if suffix.startswith("/") else base + suffix
                if u:
                    out.append((str(it.get("id") or ""), str(it.get("label") or ""), u))
            except Exception:
                continue
        return out

    def _play_episode(self, wid, lid, epid):
        d = self._json(self.api + "/data/1/work/" + wid + ".json")
        if not d:
            return ""
        line = None
        for ln in d.get("lines") or []:
            if str(ln.get("id") or "") == lid:
                line = ln
                break
        if line is None:
            lines = d.get("lines") or []
            if not lines:
                return ""
            line = lines[0]
        eps = self._resolve_playlist(line)
        if not eps:
            return ""
        for eid, label, u in eps:
            if eid == epid:
                return u
        try:
            idx = int(epid) - 1
            if 0 <= idx < len(eps):
                return eps[idx][2]
        except Exception:
            pass
        return eps[0][2]

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids
        if isinstance(ids, (list, tuple)):
            url = ids[0] if ids else ""
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if url.startswith("http") and self.isVideoFormat(url):
            return {"parse": 0, "url": url, "header": dict(self.header)}
        m = re.fullmatch(r"(\d+)@(\d+)@(\d+)", url)
        if m:
            final = self._play_episode(m.group(1), m.group(2), m.group(3))
            return {"parse": 0, "url": final, "header": dict(self.header)}
        if url.isdigit():
            d = self._json(self.api + "/data/1/work/" + url + ".json")
            if d and (d.get("lines") or []):
                line = (d.get("lines") or [])[0]
                eps = self._resolve_playlist(line)
                if eps:
                    return {"parse": 0, "url": eps[0][2], "header": dict(self.header)}
        return {"parse": 0, "url": "", "header": dict(self.header)}

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
