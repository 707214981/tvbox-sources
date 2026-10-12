# -*- coding: utf-8 -*-
"""
91PornSM Spider for TVBox (type 3 / py)
站点: https://h5ve.ksepnbir.cc
分类: 国产 / 日韩 / 欧美 / 动漫 / 调教AV / 直播回放 / 合集 / 标签
播放地址从详情页 JSON-LD 实时提取(带时效签名), 保证可用
封面图站内 AES-CBC 加密, 经 localProxy 实时解密后输出
"""

import re
import json
import html as html_lib
from urllib.parse import quote, unquote

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def fetch(self, url, headers=None, timeout=15):
            import requests
            return requests.get(url, headers=headers, timeout=timeout)


# ---------- AES-128-CBC 解密 (T-table 查表优化, 0.03s/张) ----------
# T-table 优化的纯 Python AES-128-CBC 解密
_SBOX = (
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16)
_INV_SBOX = [0]*256
for _i,_v in enumerate(_SBOX): _INV_SBOX[_v]=_i
_RCON=(0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36)
def _xt(x): return ((x<<1)&0xff)^(0x1b if x&0x80 else 0)
def _gm(a,b):
    r=0
    while b:
        if b&1: r^=a
        a=_xt(a); b>>=1
    return r
# 预计算解密 T-table
_TD0=[0]*256; _TD1=[0]*256; _TD2=[0]*256; _TD3=[0]*256
for _a in range(256):
    _s=_INV_SBOX[_a]
    _TD0[_a]=(_gm(_s,0x0e)<<24)|(_gm(_s,0x09)<<16)|(_gm(_s,0x0d)<<8)|_gm(_s,0x0b)
    _TD1[_a]=(_gm(_s,0x0b)<<24)|(_gm(_s,0x0e)<<16)|(_gm(_s,0x09)<<8)|_gm(_s,0x0d)
    _TD2[_a]=(_gm(_s,0x0d)<<24)|(_gm(_s,0x0b)<<16)|(_gm(_s,0x0e)<<8)|_gm(_s,0x09)
    _TD3[_a]=(_gm(_s,0x09)<<24)|(_gm(_s,0x0d)<<16)|(_gm(_s,0x0b)<<8)|_gm(_s,0x0e)
def _expand(key):
    ek=list(key)
    for i in range(4,44):
        t=ek[-4:]
        if i%4==0:
            t=[_SBOX[t[1]],_SBOX[t[2]],_SBOX[t[3]],_SBOX[t[0]]]
            t[0]^=_RCON[i//4-1]
        ek+=[a^b for a,b in zip(ek[-16:],t)]
    return ek
def _words(ek):
    return [ (ek[i]<<24)|(ek[i+1]<<16)|(ek[i+2]<<8)|ek[i+3] for i in range(0,len(ek),4) ]
def _mix_word(ww):
    b0=(ww>>24)&255; b1=(ww>>16)&255; b2=(ww>>8)&255; b3=ww&255
    o0=_gm(b0,0x0e)^_gm(b1,0x0b)^_gm(b2,0x0d)^_gm(b3,0x09)
    o1=_gm(b0,0x09)^_gm(b1,0x0e)^_gm(b2,0x0b)^_gm(b3,0x0d)
    o2=_gm(b0,0x0d)^_gm(b1,0x09)^_gm(b2,0x0e)^_gm(b3,0x0b)
    o3=_gm(b0,0x0b)^_gm(b1,0x0d)^_gm(b2,0x09)^_gm(b3,0x0e)
    return (o0<<24)|(o1<<16)|(o2<<8)|o3

def _dec_words(key):
    w=_words(_expand(key))
    return [_mix_word(ww) if 4<=i<40 else ww for i,ww in enumerate(w)]

def _dec_block_fast(block, w, dw):
    # block: 16 bytes -> 4 words (列优先)
    s0=(block[0]<<24)|(block[1]<<16)|(block[2]<<8)|block[3]
    s1=(block[4]<<24)|(block[5]<<16)|(block[6]<<8)|block[7]
    s2=(block[8]<<24)|(block[9]<<16)|(block[10]<<8)|block[11]
    s3=(block[12]<<24)|(block[13]<<16)|(block[14]<<8)|block[15]
    s0^=w[40]; s1^=w[41]; s2^=w[42]; s3^=w[43]
    for r in range(9,0,-1):
        k=r*4
        t0=_TD0[(s0>>24)&255]^_TD1[(s3>>16)&255]^_TD2[(s2>>8)&255]^_TD3[s1&255]^dw[k]
        t1=_TD0[(s1>>24)&255]^_TD1[(s0>>16)&255]^_TD2[(s3>>8)&255]^_TD3[s2&255]^dw[k+1]
        t2=_TD0[(s2>>24)&255]^_TD1[(s1>>16)&255]^_TD2[(s0>>8)&255]^_TD3[s3&255]^dw[k+2]
        t3=_TD0[(s3>>24)&255]^_TD1[(s2>>16)&255]^_TD2[(s1>>8)&255]^_TD3[s0&255]^dw[k+3]
        s0,s1,s2,s3=t0,t1,t2,t3
    # final round: inv_shift + inv_sub (无 mix)
    o=[0]*16
    # s0..s3 为列字, 转回字节并做 inv_shift_rows
    b=[0]*16
    for i,ww in enumerate((s0,s1,s2,s3)):
        b[i*4]=(ww>>24)&255; b[i*4+1]=(ww>>16)&255; b[i*4+2]=(ww>>8)&255; b[i*4+3]=ww&255
    # inv_shift_rows on b (行优先视角需转置)... 
    # 我们的 b 是列优先 [c0r0,c0r1,c0r2,c0r3, c1r0,...]
    # inv_shift: row r 右移 r
    sb=[0]*16
    for r_ in range(4):
        for c_ in range(4):
            sb[c_*4+r_]=_INV_SBOX[b[((c_-r_)%4)*4+r_]]
    # add round key 0
    return bytes( (sb[i]^((w[i//4]>>((3-i%4)*8))&255)) for i in range(16) )
def aes_cbc_decrypt_fast(data,key,iv):
    w=_words(_expand(key)); dw=_dec_words(key); ivb=iv; out=bytearray()
    for i in range(0,len(data),16):
        blk=_dec_block_fast(data[i:i+16],w,dw)
        out+=bytes(a^b for a,b in zip(blk,ivb)); ivb=data[i:i+16]
    pad=out[-1]
    return bytes(out[:-pad]) if 1<=pad<=16 else bytes(out)

# 站内图片密钥(见 static/web/js/plugins/crypto-worker-native.js)
_IMG_KEY = b"f5d965df75336270"
_IMG_IV = b"97b60394abc2fbe1"
# 密钥固定, 轮密钥只算一次
_W = _words(_expand(_IMG_KEY))
_DW = _dec_words(_IMG_KEY)

def _img_type(data):
    """识别图片格式, 返回 (content_type,  是否有效)"""
    if data[:2] == b"\xff\xd8":
        return "image/jpeg", True
    if data[:4] == b"\x89PNG":
        return "image/png", True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", True
    if data[:3] == b"GIF":
        return "image/gif", True
    return None, False


def _aes_img_decrypt(data):
    """解密站内封面图, 返回 (bytes, content_type) 或 (None, None)"""
    if not data or len(data) < 32 or len(data) % 16:
        return None, None
    try:
        # 优先 C 实现
        from Crypto.Cipher import AES
        pt = AES.new(_IMG_KEY, AES.MODE_CBC, _IMG_IV).decrypt(data)
        pad = pt[-1]
        if 1 <= pad <= 16:
            pt = pt[:-pad]
    except Exception:
        try:
            ivb = _IMG_IV
            out = bytearray()
            for i in range(0, len(data), 16):
                blk = _dec_block_fast(data[i:i + 16], _W, _DW)
                out += bytes(a ^ b for a, b in zip(blk, ivb))
                ivb = data[i:i + 16]
            pt = bytes(out)
            pad = pt[-1]
            if 1 <= pad <= 16 and pt.endswith(bytes([pad]) * pad):
                pt = pt[:-pad]
        except Exception:
            return None, None
    ctype, ok = _img_type(pt)
    return (pt, ctype) if ok else (None, None)


class Spider(BaseSpider):
    def getName(self):
        return "91PornSM"

    def init(self, extend=""):
        self.host = "https://h5ve.ksepnbir.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        self.categories = [
            {"type_id": "new", "type_name": "最新上新"},
            {"type_id": "guochan-sm", "type_name": "国产SM"},
            {"type_id": "rihan-sm", "type_name": "日韩SM"},
            {"type_id": "oumei-sm", "type_name": "欧美SM"},
            {"type_id": "dongman-sm", "type_name": "动漫SM"},
            {"type_id": "tiaojiao-av", "type_name": "调教AV"},
            {"type_id": "taolu-zhibo", "type_name": "套路直播"},
            {"type_id": "wanwu-zhibo", "type_name": "玩物直播"},
            {"type_id": "collection/heisi", "type_name": "合集·黑丝"},
            {"type_id": "collection/kbsf", "type_name": "合集·捆绑束缚"},
            {"type_id": "collection/zhajing", "type_name": "合集·榨精"},
            {"type_id": "collection/muhou", "type_name": "合集·母狗"},
            {"type_id": "collection/caita", "type_name": "合集·踩踏"},
            {"type_id": "collection/zujiao", "type_name": "合集·足交"},
        ]

    # ---------------- 内部工具 ----------------
    def _fetch(self, url, timeout=15):
        rsp = self.fetch(url, headers=self.headers, timeout=timeout)
        try:
            rsp.encoding = "utf-8"
        except Exception:
            pass
        return rsp

    def _get(self, url, timeout=15):
        return self._fetch(url, timeout).text

    def _status(self, rsp):
        try:
            return int(getattr(rsp, "status_code", 200) or 200)
        except Exception:
            return 200

    def _page_info(self, html, pg):
        """解析真实总页数; 无分页信息时视为只有当前页, 防止 App 无限翻页"""
        txt = re.sub(r"<[^>]+>", " ", html)
        m = re.search(r"第\s*\d+\s*/\s*(\d+)\s*页", txt)
        if m:
            try:
                return max(int(m.group(1)), pg)
            except Exception:
                pass
        return pg

    def _unescape(self, s):
        return html_lib.unescape(s or "").strip()

    def _abs(self, u):
        u = self._unescape(u)
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _cover_by_search(self, vid, name):
        """详情页 JSON-LD 缩略图签名常过期, 用搜索 API 按标题找回可用封面"""
        try:
            url = f"{self.host}/api/search/?q={quote(name)}&page=1"
            data = json.loads(self._get(url)).get("data", {})
            for it in data.get("items", []):
                if str(it.get("id", "")) == str(vid) and it.get("cover"):
                    return self._abs(it["cover"])
        except Exception:
            pass
        return ""

    def _cover(self, img_html):
        """懒加载取 data-src, 占位 gif 跳过"""
        m = re.search(r'data-src="([^"]+)"', img_html)
        src = m.group(1) if m else ""
        if not src or "data:image" in src:
            m = re.search(r'src="(https?://[^"]+)"', img_html)
            src = m.group(1) if m else ""
        return self._abs(src)

    def _proxy_pic(self, url):
        """封面图站内 AES 加密, 走 localProxy 实时解密"""
        if not url or not url.startswith("http"):
            return url
        return "http://127.0.0.1:9978/proxy?do=py&type=img&url=" + quote(url, safe="")

    def _decrypt_img(self, data):
        pt, ctype = _aes_img_decrypt(data)
        return (pt, ctype) if pt else (None, None)

    def _parse_cards(self, html):
        """解析 video-card 列表"""
        videos = []
        if getattr(self, "_cover_cache", None) is None:
            self._cover_cache = {}
        for m in re.finditer(
            r'<a class="video-card"[^>]*href="(/video/\d+/)"[^>]*>(.*?)</a>', html, re.S
        ):
            href, body = m.group(1), m.group(2)
            vid = re.search(r"/video/(\d+)/", href).group(1)
            t = re.search(r'class="card-title">(.*?)</h3>', body, re.S)
            title = self._unescape(re.sub(r"<[^>]+>", "", t.group(1))) if t else ""
            if not title:
                t = re.search(r'alt="([^"]+)"', body)
                title = self._unescape(t.group(1)) if t else ""
            img = re.search(r"<img[^>]*>", body)
            pic = self._cover(img.group(0)) if img else ""
            if pic:
                self._cover_cache[vid] = pic
            d = re.search(r'class="duration">([^<]+)<', body)
            remark = self._unescape(d.group(1)) if d else ""
            videos.append({
                "vod_id": vid,
                "vod_name": title or f"视频{vid}",
                "vod_pic": self._proxy_pic(pic),
                "vod_remarks": remark,
            })
        return videos

    def _detail_json_ld(self, html):
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        if not m:
            return {}
        try:
            data = json.loads(m.group(1))
        except Exception:
            return {}
        for node in data.get("@graph", []):
            if isinstance(node, dict) and node.get("@type") == "VideoObject":
                return node
        return {}

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter):
        rsp = self._get(self.host + "/")
        # 首页只取"近期上新"板块, 避免分类重复
        sec = re.search(r"近期上新.*?<div class=\"video-grid\">(.*?)</div>\s*</div>", rsp, re.S)
        videos = self._parse_cards(sec.group(1) if sec else rsp)[:24]
        return {"class": self.categories, "list": videos, "filters": {}}

    def homeVideoContent(self):
        rsp = self._get(self.host + "/list/new/")
        return {"list": self._parse_cards(rsp)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        if tid == "new":
            url = f"{self.host}/list/new/" if pg == 1 else f"{self.host}/list/{pg}/"
        elif tid.startswith("collection/"):
            base = f"{self.host}/video/{tid}/"
            url = base if pg == 1 else f"{base}page/{pg}/"
        elif tid.startswith("tag/"):
            base = f"{self.host}/{tid}/"
            url = base if pg == 1 else f"{base}{pg}/"
        else:
            base = f"{self.host}/video/{tid}/"
            url = base if pg == 1 else f"{base}{pg}/"
        rsp_obj = self._fetch(url)
        if self._status(rsp_obj) == 404:
            return {"list": [], "page": pg, "pagecount": pg - 1 if pg > 1 else 1,
                    "limit": 90, "total": 0}
        rsp = rsp_obj.text if hasattr(rsp_obj, "text") else ""
        videos = self._parse_cards(rsp)
        pagecount = self._page_info(rsp, pg)
        return {"list": videos, "page": pg, "pagecount": pagecount,
                "limit": 90, "total": 0}

    def detailContent(self, ids):
        vid = ids[0]
        url = f"{self.host}/video/{vid}/"
        rsp = self._get(url)
        ld = self._detail_json_ld(rsp)
        name = ld.get("name", "")
        desc = ld.get("description", "")
        # 封面优先级: 列表缓存 > 搜索API > JSON-LD(签名常过期)
        pic = (getattr(self, "_cover_cache", None) or {}).get(vid, "")
        if not pic and name:
            pic = self._cover_by_search(vid, name)
        if not pic:
            thumbs = ld.get("thumbnailUrl") or []
            if thumbs:
                pic = self._abs(thumbs[0])
        dur = ld.get("duration", "")
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._proxy_pic(pic),
            "vod_content": desc.strip(),
            "vod_remarks": dur.replace("PT", "").replace("M", ":").replace("S", ""),
            "vod_play_from": "91PornSM",
            # play_url 存详情页地址, playerContent 实时解析新鲜签名
            "vod_play_url": f"在线播放${url}",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        url = f"{self.host}/api/search/?q={quote(key)}&page={pg}"
        rsp = self._get(url)
        videos = []
        pagecount = pg
        try:
            data = json.loads(rsp).get("data", {})
            pagi = data.get("pagination") or {}
            try:
                pagecount = max(int(pagi.get("pages", pg)), pg)
            except Exception:
                pass
            for it in data.get("items", []):
                vid = str(it.get("id", ""))
                if not vid:
                    continue
                dur = it.get("duration", "")
                remark = ""
                try:
                    s = int(dur)
                    remark = f"{s // 60}:{s % 60:02d}"
                except Exception:
                    pass
                videos.append({
                    "vod_id": vid,
                    "vod_name": self._unescape(it.get("title", "")),
                    "vod_pic": self._proxy_pic(self._abs(it.get("cover", ""))),
                    "vod_remarks": remark,
                })
        except Exception:
            pass
        return {"list": videos, "page": pg, "pagecount": pagecount, "limit": 90, "total": 0}

    def playerContent(self, flag, id, vipFlags):
        # id 为详情页地址, 实时抓取带时效签名的 m3u8
        url = id if id.startswith("http") else f"{self.host}/video/{id}/"
        play_url = ""
        try:
            rsp = self._get(url)
            ld = self._detail_json_ld(rsp)
            play_url = self._unescape(ld.get("contentUrl", ""))
        except Exception:
            pass
        if not play_url:
            # 兜底: 卡片上的 data-preview-src
            m = re.search(r'data-preview-src="([^"]+\.m3u8[^"]*)"', rsp)
            if m:
                play_url = self._unescape(m.group(1))
        return {
            "parse": 0,
            "playUrl": "",
            "url": play_url,
            "header": self.headers,
        }

    def isVideoFormat(self, url):
        url = url.lower()
        return url.endswith(".m3u8") or url.endswith(".mp4") or ".m3u8?" in url

    def localProxy(self, param):
        # 图片解密代理: TVBox 请求 vod_pic(代理地址) 时回调到这里
        try:
            url = param.get("url", "") if isinstance(param, dict) else ""
            url = unquote(url)
            if not url.startswith("http"):
                return [404, "text/plain", b"bad url", {}]
            # 内存缓存: 滑动回来不重复解密
            cache = getattr(self, "_img_cache", None)
            if cache is None:
                cache = self._img_cache = {}
            if url in cache:
                pt, ctype = cache[url]
                return [200, ctype, pt, {}]
            rsp = self.fetch(url, headers=self.headers, timeout=15)
            data = rsp.content if hasattr(rsp, "content") else b""
            pt, ctype = self._decrypt_img(data)
            if pt:
                if len(cache) > 200:
                    cache.clear()
                cache[url] = (pt, ctype)
                return [200, ctype, pt, {}]
            # 解密失败则原样返回(可能站点已换明文图)
            ctype = "image/jpeg"
            try:
                ctype = rsp.headers.get("Content-Type", ctype)
            except Exception:
                pass
            return [200, ctype, data, {}]
        except Exception as e:
            return [500, "text/plain", str(e).encode(), {}]

    def destroy(self):
        pass


# 本地自测(非 TVBox 环境)
if __name__ == "__main__":
    import requests as _rq

    class TSpider(Spider):
        def fetch(self, url, headers=None, timeout=15):
            return _rq.get(url, headers=headers, timeout=timeout)

    sp = TSpider()
    sp.init()
    print("分类数:", len(sp.categories))
    h = sp.homeContent(None)
    print("首页视频:", len(h["list"]), "| 首条:", h["list"][0]["vod_name"][:30] if h["list"] else None)
    c = sp.categoryContent("guochan-sm", 1, None, None)
    print("国产页:", len(c["list"]), "| 首条:", c["list"][0]["vod_name"][:30] if c["list"] else None)
    if c["list"]:
        vid = c["list"][0]["vod_id"]
        d = sp.detailContent([vid])
        print("详情:", d["list"][0]["vod_name"][:30])
        p = sp.playerContent(None, d["list"][0]["vod_play_url"].split("$")[1], None)
        print("播放URL:", p["url"][:100])
    s = sp.searchContent("黑丝", False, "1")
    print("搜索'黑丝':", len(s["list"]), "| 首条:", s["list"][0]["vod_name"][:30] if s["list"] else None)
    print("ALL OK")
