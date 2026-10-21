import re, json, base64, html
try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:
    def __init__(self):
        self.site = "http://wapi.kuwo.cn"
        self.name = "酷我音乐"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": "http://www.kuwo.cn/",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "*/*",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._play_ua = "Mozilla/5.0 (Linux; Android 10)"
        self._defpic = "https://image.kuwo.cn/newvip/icon/100.ico"
        self._cats = [
            {"type_id": "bang:16", "type_name": "热歌榜"},
            {"type_id": "bang:17", "type_name": "新歌榜"},
            {"type_id": "bang:93", "type_name": "飙升榜"},
            {"type_id": "ac:1", "type_name": "华语男"},
            {"type_id": "ac:2", "type_name": "华语女"},
            {"type_id": "ac:3", "type_name": "华语组合"},
            {"type_id": "ac:4", "type_name": "日韩男"},
            {"type_id": "ac:5", "type_name": "日韩女"},
            {"type_id": "ac:6", "type_name": "日韩组合"},
            {"type_id": "ac:7", "type_name": "欧美男"},
            {"type_id": "ac:8", "type_name": "欧美女"},
            {"type_id": "ac:9", "type_name": "欧美组合"},
            {"type_id": "ac:0", "type_name": "其他"},
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

    def _get(self, url, referer=None, ua=None):
        h = dict(self.header)
        if ua:
            h["User-Agent"] = ua
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

    def _getj(self, url, referer=None, ua=None):
        try:
            return json.loads(self._get(url, referer=referer, ua=ua) or "")
        except Exception:
            return {}

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
        if not s:
            return ""
        s = html.unescape(str(s))
        s = re.sub(r"<[^>]+>", "", s).replace("\xa0", " ").replace("&nbsp;", " ").strip()
        return s

    def _b64e(self, s):
        return base64.urlsafe_b64encode(s.encode("utf-8")).decode().rstrip("=")

    def _b64d(self, s):
        try:
            s = str(s or "")
            s += "=" * (-len(s) % 4)
            return base64.urlsafe_b64decode(s).decode("utf-8")
        except Exception:
            return ""

    def _safe_name(self, s):
        return str(s or "").replace("#", "").replace("$", "").strip()

    def _song_vod(self, name, rid, artist="", pic=""):
        name = self._clean(name)
        rid = str(rid or "")
        return {
            "vod_id": "ksong:%s:%s" % (rid, self._b64e(name)),
            "vod_name": name,
            "vod_pic": self._u(pic) if pic else self._defpic,
            "vod_remarks": self._clean(artist),
        }

    def _chart_songs(self, bang_id, pg):
        url = ("http://wapi.kuwo.cn/api/www/bang/bang/musicList?bangId=%s&pn=%d&rn=30"
               % (bang_id, pg))
        d = self._getj(url)
        arr = ((d.get("data") or {}).get("musicList")) or []
        out = []
        for it in arr:
            rid = str(it.get("rid") or "")
            if not rid:
                continue
            out.append(self._song_vod(it.get("name"), rid, it.get("artist"), it.get("pic")))
        return out

    def _artists(self, tid, pg):
        url = ("http://wapi.kuwo.cn/api/www/artist/artistInfo?category=%s&prefix=&pn=%d&rn=30"
               % (tid, pg))
        d = self._getj(url)
        arr = ((d.get("data") or {}).get("artistList")) or []
        out = []
        for it in arr:
            aid = str(it.get("id") or "")
            if not aid:
                continue
            pic = it.get("pic300") or it.get("pic") or it.get("pic120") or ""
            out.append({
                "vod_id": "artist:%s" % aid,
                "vod_name": self._clean(it.get("name")),
                "vod_pic": self._u(pic) if pic else self._defpic,
                "vod_remarks": "",
            })
        return out

    def _artist_songs(self, aid):
        songs = []
        for p in range(1, 11):
            url = ("http://wapi.kuwo.cn/api/www/artist/artistMusic?artistid=%s&pn=%d&rn=30"
                   % (aid, p))
            d = self._getj(url)
            if d.get("code") != 200:
                break
            arr = ((d.get("data") or {}).get("list")) or []
            if not arr:
                break
            for it in arr:
                name = str(it.get("name") or "").replace("$", "").replace("#", "").strip()
                rid = str(it.get("rid") or "")
                if name and rid:
                    songs.append((name, rid))
            if len(songs) >= 300:
                break
        return songs[:300]

    def _artist_name(self, aid):
        d = self._getj("http://wapi.kuwo.cn/api/www/artist/artist?artistid=%s" % aid)
        if d.get("code") == 200:
            return self._clean((d.get("data") or {}).get("name"))
        return ""

    # 音质: (quality_id, bitrate, format)
    _QUALS = (("320", "320", "mp3"), ("2000", "2000", "flac"), ("128", "128", "mp3"))
    _QUAL_FROM = "高品质$$$无损$$$标准"

    def _resolve_url(self, rid, quality="320"):
        bitrate, fmt = "320", "mp3"
        for q, b, f in self._QUALS:
            if q == str(quality):
                bitrate, fmt = b, f
                break
        url = ("https://nmobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayer_ar_4.4.2.7_B_nuoweida_vh.apk"
               "&type=convert_url_with_sign&rid=%s&bitrate=%s&format=%s" % (rid, bitrate, fmt))
        d = self._getj(url, referer="http://www.kuwo.cn/", ua=self._play_ua)
        if d.get("code") == 200:
            return str((d.get("data") or {}).get("url") or "")
        return ""

    def init(self, extend=""):
        pass

    def homeContent(self, filter=None):
        return {"class": self._cats, "list": self._chart_songs("16", 1)}

    def homeVideoContent(self):
        return {"list": self._chart_songs("16", 1)}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        t = str(tid or "")
        if t.startswith("bang:"):
            bang_id = t.split(":", 1)[1]
            vod_list = self._chart_songs(bang_id, pg)
            return {"list": vod_list, "page": pg, "pagecount": 4,
                    "limit": 30, "total": 100}
        if t.startswith("ac:"):
            cat = t.split(":", 1)[1]
            vod_list = self._artists(cat, pg)
            pagecount = pg + 1 if len(vod_list) >= 30 else pg
            return {"list": vod_list, "page": pg, "pagecount": pagecount,
                    "limit": 30, "total": pagecount * 30}
        return {"list": [], "page": pg, "pagecount": 1, "limit": 30, "total": 0}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = str(vid or "").strip()
        if vid.startswith("artist:"):
            aid = vid.split(":", 1)[1]
            name = self._artist_name(aid) or "歌手"
            songs = self._artist_songs(aid)
            play_url = "$$$".join(
                "#".join("%s$kplay:%s:%s" % (self._safe_name(n), q, r) for n, r in songs)
                for q, _, _ in self._QUALS)
            return {"list": [{
                "vod_id": vid, "vod_name": name, "vod_pic": self._defpic,
                "vod_content": "%s 全部歌曲（%d 首）" % (name, len(songs)),
                "vod_play_from": self._QUAL_FROM, "vod_play_url": play_url,
            }]}
        if vid.startswith("ksong:"):
            parts = vid.split(":", 2)
            rid = parts[1] if len(parts) > 1 else ""
            name = self._b64d(parts[2]) if len(parts) > 2 else ""
            if not name:
                name = "歌曲" + rid
            play_url = "$$$".join(
                "%s$kplay:%s:%s" % (self._safe_name(name), q, rid) for q, _, _ in self._QUALS)
            return {"list": [{
                "vod_id": vid, "vod_name": name, "vod_pic": self._defpic,
                "vod_content": name,
                "vod_play_from": self._QUAL_FROM,
                "vod_play_url": play_url,
            }]}
        return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            from urllib.parse import quote
            url = ("https://search.kuwo.cn/r.s?all=%s&ft=music&itemset=web_2013"
                   "&client=kt&pn=0&rn=30&rformat=json&encoding=utf8" % quote(str(key)))
        except Exception:
            return {"list": []}
        txt = self._get(url)
        if not txt:
            return {"list": []}
        out, seen = [], set()
        for m in re.finditer(r"'SONGNAME':'(.*?)'.*?'ARTIST':'(.*?)'.*?'MUSICRID':'MUSIC_(\d+)'",
                             txt, re.S):
            rid = m.group(3)
            if rid in seen:
                continue
            seen.add(rid)
            out.append(self._song_vod(m.group(1), rid, m.group(2), ""))
        return {"list": out}

    def playerContent(self, flag, ids, vipFlags=None):
        rid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        rid = str(rid or "").strip()
        if rid.startswith("kplay:"):
            rid = rid[len("kplay:"):]
        quality = "320"
        if ":" in rid:
            q, _, r = rid.partition(":")
            if q in ("2000", "320", "128"):
                quality, rid = q, r
        if not rid:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        return {"parse": 0, "url": self._resolve_url(rid, quality), "header": dict(self.header)}

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
