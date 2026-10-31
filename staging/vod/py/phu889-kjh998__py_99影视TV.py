# -*- coding: utf-8 -*-
# 99影视TV - https://99itv.cc (修正完整版：精準 7 槽位 /show/ 分頁、動態子分類與篩選器槽位自動識別)
import re
import json
import gzip
import zlib
import ssl
import time
import random
import urllib.parse
import urllib.request
from base.spider import Spider

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass


class Spider(Spider):
    def __init__(self):
        self.host = 'https://99itv.cc'
        self.ua = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/131.0.0.0 Safari/537.36'
        )
        self.headers = {
            'User-Agent': self.ua,
            'Referer': self.host + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,zh-CN;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
        }
        self.timeout = 15
        self.last = 0

        # 四大主分類
        self.main_classes = [
            {'type_id': 'movie', 'type_name': '电影'},
            {'type_id': 'drama', 'type_name': '电视剧'},
            {'type_id': 'variety', 'type_name': '综艺'},
            {'type_id': 'anime', 'type_name': '动漫'},
        ]
        self.classes = list(self.main_classes)
        self.filters = {}
        self._loaded_meta = False

    def getName(self):
        return '99影视TV'

    def init(self, extend=''):
        pass

    def getDependence(self):
        return []

    def destroy(self):
        pass

    def _log(self, msg):
        try:
            print('[99影视TV] ' + str(msg))
        except Exception:
            pass

    def _clean(self, s):
        if not s:
            return ''
        s = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', '', str(s), flags=re.I)
        s = re.sub(r'<[^>]+>', ' ', s)
        try:
            import html
            s = html.unescape(s)
        except Exception:
            pass
        return re.sub(r'\s+', ' ', s).strip()

    def _fix(self, url):
        if not url:
            return ''
        url = str(url).strip().replace('&amp;', '&')
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        if not re.match(r'https?://', url, re.I):
            return self.host + '/' + url.lstrip('/')
        return url

    def _anti(self, html):
        return bool(html and any(x in html for x in ['請不要頻繁操作', '搜索時間間隔', '系統提示', '等待時間']))

    def _get(self, url, referer=None, retry=3):
        url = self._fix(url)
        for i in range(retry):
            try:
                wait = 0.35 - (time.time() - self.last)
                if wait > 0:
                    time.sleep(wait + random.uniform(0.05, 0.15))
                h = dict(self.headers)
                if referer:
                    h['Referer'] = referer
                req = urllib.request.Request(url, headers=h)
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as r:
                    raw = r.read()
                    enc = (r.info().get('Content-Encoding') or '').lower()
                    if enc == 'gzip':
                        raw = gzip.decompress(raw)
                    elif enc == 'deflate':
                        try:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                        except Exception:
                            raw = zlib.decompress(raw)
                    self.last = time.time()
                    text = raw.decode('utf-8', errors='ignore')
                    if self._anti(text):
                        self._log('觸發頻率限制: ' + url)
                        time.sleep(1.2 + i)
                        continue
                    return text
            except Exception as e:
                self._log('請求失敗(%s/%s): %s %s' % (i + 1, retry, url, e))
                time.sleep(0.6 + i)
        return ''

    def _vid_from_href(self, href):
        href = href or ''
        m = re.search(r'/detail/([^"/]+?)\.html', href)
        return m.group(1) if m else ''

    def _parse_items(self, html):
        """
        只解析真正的海報/卡片區塊，排除頁面頂部搜尋框熱搜榜與側邊欄的純文字連結
        """
        arr, seen = [], set()
        if not html:
            return arr

        # 優先匹配 MXPro 標準海報卡片 <a class="...module-poster-item...">...</a>
        blocks = re.findall(
            r'<a[^>]+class="[^"]*module-(?:poster|card)-item[^"]*"[^>]*>[\s\S]*?</a>',
            html,
            flags=re.I,
        )
        if not blocks:
            blocks = re.findall(
                r'<div[^>]+class="[^"]*module-(?:poster|card)-item[^"]*"[^>]*>[\s\S]*?</div>',
                html,
                flags=re.I,
            )
        if not blocks:
            # 備用：只抓取內部含有 <img> 標籤的 /detail/ 連結，排除純文字熱搜榜
            all_a = re.findall(r'<a[^>]+href="[^"]*/detail/[^"]+\.html"[\s\S]*?</a>', html, re.I)
            blocks = [b for b in all_a if re.search(r'<img[^>]+(?:data-original|data-src|src)=', b, re.I)]

        for it in blocks:
            try:
                hm = re.search(r'href="([^"]*/detail/[^"]+\.html)"', it, re.I)
                if not hm:
                    continue
                vid = self._vid_from_href(hm.group(1))
                if not vid or vid in seen:
                    continue

                pic = ''
                pm = re.search(r'(?:data-original|data-src|src)="([^"]+)"', it, re.I)
                if pm:
                    pic = self._fix(pm.group(1))
                # 排除無圖片之純文字導覽或排行榜連結
                if not pic:
                    continue

                seen.add(vid)
                title = ''
                for p in [
                    r'title="([^"]+)"',
                    r'alt="([^"]+)"',
                    r'class="[^"]*module-poster-item-title[^"]*"[^>]*>([\s\S]*?)<',
                    r'<strong[^>]*>([\s\S]*?)</strong>',
                    r'class="[^"]*title[^"]*"[^>]*>([\s\S]*?)<',
                ]:
                    m = re.search(p, it, re.I)
                    if m:
                        title = self._clean(m.group(1))
                        if title:
                            break
                if not title:
                    title = self._clean(it)

                remark = ''
                rm = re.search(r'class="[^"]*module-item-note[^"]*"[^>]*>([\s\S]*?)</', it, re.I)
                if rm:
                    remark = self._clean(rm.group(1))

                if title:
                    arr.append({
                        'vod_id': vid,
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': remark,
                    })
            except Exception as e:
                self._log('列表單條解析失敗: ' + str(e))
        return arr

    def _parse_pagecount(self, html, current_page, item_count):
        """
        精準解析 /show/{s0}-{s1}-{s2}-{s3}-{s4}-{s5}-{s6}.html 中的第 4 個欄位 (索引 3 = page)
        例如 /show/action---88---.html -> parts[3] == '88'
        """
        max_page = current_page
        if html:
            for m in re.finditer(r'href="[^"]*/show/([^/"\']+?)\.html"', html, re.I):
                slug = m.group(1)
                parts = slug.split('-')
                if len(parts) == 7 and parts[3].isdigit():
                    p = int(parts[3])
                    if p > max_page:
                        max_page = p
            # 相容備用：直接尋找「尾頁」或最後一頁文字旁的連結
            if max_page == current_page:
                for m in re.finditer(r'/show/[^/"\']+?-(\d+)-[a-zA-Z0-9_%-]*\.html', html, re.I):
                    p = int(m.group(1))
                    if current_page < p < 1900 and p > max_page:
                        max_page = p

        # 若頁面上仍有充足影片但未解析到尾頁，至少保留下一頁 (current_page + 1) 以支援無限下拉翻頁
        if max_page <= current_page and item_count >= 12:
            return current_page + 1
        return max_page

    def _parse_filter_rows_from_show_html(self, html, base_tid):
        """
        直接從 /show/{base_tid}------.html 的 DOM 篩選列解析：
        1. 提取「類型」子分類 (Slot 0 改變者)
        2. 自動比對 7 個槽位 (Slot 0~6)，識別每個篩選項目實際修改的槽位索引，編碼為 'slotIdx:val'
        """
        sub_cats = []
        filter_list = []
        if not html:
            return sub_cats, filter_list

        # 找出所有包含篩選連結的區塊（支援 MXPro 的 module-item-box / library-box / scroll-content 等容器）
        row_blocks = re.findall(
            r'<(?:div|dl)[^>]+class="[^"]*(?:module-item-box|library-box|scroll-box|hl-filter-item|fed-screen-list)[^"]*"[\s\S]*?</(?:div|dl)>',
            html,
            flags=re.I,
        )
        if not row_blocks:
            # 退回以「類型/劇情/地區/語言/年份/字母/排序」標題切分區塊
            row_blocks = re.findall(
                r'(?:类型|剧情|分类|地区|语言|年份|年代|字母|排序)[\s\S]{1,3500}?(?=(?:类型|剧情|分类|地区|语言|年份|年代|字母|排序|<div[^>]+class="[^"]*module-items|$))',
                html,
                flags=re.I,
            )

        for idx, block in enumerate(row_blocks):
            links = re.findall(r'<a[^>]+href="[^"]*/show/([^/"\']+?)\.html"[^>]*>([\s\S]*?)</a>', block, re.I)
            if not links:
                continue

            # 判斷該列名稱
            row_text = self._clean(block[:120])
            row_name = '篩選%d' % (idx + 1)
            for label in ['类型', '剧情', '分类', '地区', '语言', '年份', '年代', '字母', '排序']:
                if label in row_text:
                    row_name = label
                    break

            options = [{'n': '全部', 'v': ''}]
            seen_vals = set([''])

            for slug, raw_name in links:
                name = self._clean(raw_name)
                if not name or name in ['全部', '全部类型', '全部地区', '全部年份'] or '片库' in name or '首页' in name:
                    continue
                parts = slug.split('-')
                if len(parts) != 7:
                    continue

                # 檢查哪一個槽位 (0~6, 排除 3=page) 與預設值不同
                changed_slot = -1
                changed_val = ''
                if parts[0] != base_tid and all(parts[k] == '' for k in [1, 2, 4, 5, 6]):
                    changed_slot = 0
                    changed_val = parts[0]
                else:
                    for s_idx in [1, 2, 4, 5, 6]:
                        if parts[s_idx] != '':
                            changed_slot = s_idx
                            changed_val = parts[s_idx]
                            break

                if changed_slot == 0:
                    # Slot 0 為子分類 (例如 action=动作片, comedy=喜剧片)
                    if changed_val not in [c['type_id'] for c in sub_cats]:
                        sub_cats.append({'type_id': changed_val, 'type_name': name})
                    enc_v = '0:' + changed_val
                elif changed_slot > 0:
                    enc_v = '%d:%s' % (changed_slot, changed_val)
                else:
                    # 若點擊的是「時間排序」等預設連結（與空槽位相同），其值設為空字串避免汙染槽位
                    enc_v = ''

                if enc_v and enc_v not in seen_vals:
                    seen_vals.add(enc_v)
                    options.append({'n': name, 'v': enc_v})

            if len(options) > 1:
                filter_list.append({
                    'key': 'slot_%d' % idx,
                    'name': row_name,
                    'value': options,
                })

        return sub_cats, filter_list

    def _load_categories_and_filters(self):
        if self._loaded_meta:
            return
        self._loaded_meta = True

        all_classes = list(self.main_classes)
        seen_type_ids = set(c['type_id'] for c in all_classes)

        for main_cat in self.main_classes:
            mid = main_cat['type_id']
            html = self._get('/show/%s------.html' % mid)
            sub_cats, flist = self._parse_filter_rows_from_show_html(html, mid)
            if flist:
                self.filters[mid] = flist

            for sc in sub_cats:
                sid = sc['type_id']
                if sid not in seen_type_ids:
                    seen_type_ids.add(sid)
                    all_classes.append(sc)
                # 子分類繼承除「類型(Slot 0)」以外的篩選列（地区、年份、排序等）
                if sid not in self.filters and flist:
                    sub_flist = [f for f in flist if not any(v['v'].startswith('0:') for v in f['value'] if v['v'])]
                    if sub_flist:
                        self.filters[sid] = sub_flist

        self.classes = all_classes

    def _build_show_url(self, tid, page=1, extend=None):
        """
        組裝 7 槽位 (6 個 '-') 片庫網址：
        /show/{slot0}-{slot1}-{slot2}-{slot3:page}-{slot4}-{slot5}-{slot6}.html
        - 第 1 頁預設：/show/action------.html
        - 第 2 頁預設：/show/action---2---.html
        """
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}

        slots = [str(tid).strip(), '', '', '', '', '', '']
        if int(page) > 1:
            slots[3] = str(int(page))

        # 套用透過 DOM 自動識別出的 'slotIdx:val' 篩選參數
        for k, v in extend.items():
            if not v or not isinstance(v, str):
                continue
            v = v.strip()
            if ':' in v:
                s_idx_str, s_val = v.split(':', 1)
                if s_idx_str.isdigit():
                    s_idx = int(s_idx_str)
                    if 0 <= s_idx <= 6 and s_idx != 3:
                        slots[s_idx] = s_val

        return '/show/' + '-'.join(slots) + '.html'

    def homeContent(self, filter=False):
        self._load_categories_and_filters()
        res = {'class': self.classes, 'list': []}
        if filter:
            res['filters'] = self.filters
        html = self._get(self.host + '/')
        res['list'] = self._parse_items(html)[:30]
        return res

    def homeVideoContent(self):
        html = self._get(self.host + '/')
        return {'list': self._parse_items(html)[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1

        url = self._build_show_url(tid, page, extend)
        html = self._get(url)
        items = self._parse_items(html)

        pagecount = self._parse_pagecount(html, page, len(items))
        limit = len(items) if items else 48
        return {
            'list': items,
            'page': page,
            'pagecount': pagecount,
            'limit': limit,
            'total': pagecount * limit,
        }

    def searchContent(self, key, quick=False, pg=None):
        if not key:
            return {'list': []}
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        wd = urllib.parse.quote(str(key).strip())
        urls = ['/search.html?wd=%s' % wd, '/search/wd/%s.html' % wd]
        if page > 1:
            urls.insert(0, '/search/page/%s/wd/%s.html' % (page, wd))
        items = []
        for u in urls:
            html = self._get(u)
            items = self._parse_items(html)
            if items:
                break
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': 20,
            'total': len(items),
        }

    def detailContent(self, ids):
        res = {'list': []}
        if not ids:
            return res
        vid = str(ids[0])
        html = self._get('/detail/%s.html' % vid)
        if not html:
            return res
        vod = {
            'vod_id': vid,
            'vod_name': '',
            'vod_pic': '',
            'vod_content': '',
            'vod_director': '',
            'vod_actor': '',
            'vod_remarks': '',
            'vod_play_from': '',
            'vod_play_url': '',
        }
        m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I)
        if m:
            vod['vod_name'] = self._clean(m.group(1))
        pm = re.search(r'class="[^"]*module-info-poster[^"]*"[\s\S]*?<img[^>]+(?:data-original|data-src|src)="([^"]+)"', html, re.I)
        if not pm:
            pm = re.search(r'property="og:image"\s+content="([^"]+)"', html, re.I)
        if pm:
            vod['vod_pic'] = self._fix(pm.group(1))
        dm = re.search(r'class="[^"]*module-info-introduction-content[^"]*"[^>]*>([\s\S]*?)</div>', html, re.I)
        if dm:
            vod['vod_content'] = self._clean(dm.group(1))
        for key, field in [('導演', 'vod_director'), ('主演', 'vod_actor'), ('備註', 'vod_remarks')]:
            mm = re.search(key + r'[：:]?[\s\S]{0,80}?class="[^"]*module-info-item-content[^"]*"[^>]*>([\s\S]*?)</div>', html, re.I)
            if mm:
                vod[field] = self._clean(mm.group(1)).replace(' / ', ',')

        tabs = re.findall(r'class="[^"]*module-tab-item[^"]*"[^>]*data-dropdown-value="([^"]+)"[\s\S]*?<span[^>]*>([\s\S]*?)</span>', html, re.I)
        names = [self._clean(b) or self._clean(a) for a, b in tabs]
        blocks = re.findall(r'<div[^>]+class="[^"]*module-play-list-content[^"]*"[^>]*>([\s\S]*?)</div>', html, re.I)
        play_from, play_url = [], []
        for i, block in enumerate(blocks):
            eps, seen = [], set()
            for href, name in re.findall(r'<a[^>]+href="([^"]*?/userpy/[^"]+\.html)"[\s\S]*?<span[^>]*>([\s\S]*?)</span>', block, re.I):
                try:
                    purl = self._fix(href)
                    if purl in seen:
                        continue
                    seen.add(purl)
                    eps.append('%s$%s' % (self._clean(name) or ('第%s集' % (len(eps) + 1)), purl))
                except Exception:
                    continue
            if eps:
                play_from.append(names[i] if i < len(names) and names[i] else '線路%s' % (i + 1))
                play_url.append('#'.join(eps))
        if not play_url:
            eps, seen = [], set()
            for href, name in re.findall(r'<a[^>]+href="([^"]*?/userpy/[^"]+\.html)"[\s\S]*?<span[^>]*>([\s\S]*?)</span>', html, re.I):
                purl = self._fix(href)
                if purl not in seen:
                    seen.add(purl)
                    eps.append('%s$%s' % (self._clean(name), purl))
            if eps:
                play_from = ['默認']
                play_url = ['#'.join(eps)]
        vod['vod_play_from'] = '$$$'.join(play_from)
        vod['vod_play_url'] = '$$$'.join(play_url)
        res['list'].append(vod)
        return res

    def _decode_player_url(self, data):
        url = data.get('url') or ''
        enc = str(data.get('encrypt', '0'))
        try:
            if enc == '1':
                url = urllib.parse.unquote(url)
            elif enc == '2':
                import base64
                url = base64.b64decode(urllib.parse.unquote(url)).decode('utf-8', errors='ignore')
            else:
                url = urllib.parse.unquote(url)
        except Exception as e:
            self._log('播放地址解碼異常: ' + str(e))
        return self._fix(url)

    def _media_header(self, referer):
        return json.dumps({
            'User-Agent': self.ua,
            'Referer': referer or self.host + '/',
            'Origin': self.host,
        }, ensure_ascii=False)

    def playerContent(self, flag, id, vipFlags=None):
        ret = {'parse': 1, 'playUrl': '', 'url': id or '', 'header': ''}
        if not id:
            return ret
        full = self._fix(id)
        if re.search(r'\.(m3u8|mp4|flv)(\?|$)', full, re.I):
            return {'parse': 0, 'playUrl': '', 'url': full, 'header': self._media_header(self.host + '/')}
        html = self._get(full, self.host + '/')
        if html:
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', html, re.I)
            if not m:
                m = re.search(r'var\s+player_\w+\s*=\s*(\{[\s\S]*?\})\s*;', html, re.I)
            if m:
                try:
                    data = json.loads(m.group(1))
                    purl = self._decode_player_url(data)
                    if purl and re.search(r'\.(m3u8|mp4|flv)(\?|$)', purl, re.I):
                        return {'parse': 0, 'playUrl': '', 'url': purl, 'header': self._media_header(full)}
                    if purl:
                        return {'parse': 1, 'playUrl': '', 'url': purl, 'header': self._media_header(full)}
                except Exception as e:
                    self._log('player_aaaa解析失敗: ' + str(e))
            im = re.search(r'<iframe[^>]+src="([^"]+)"', html, re.I)
            if im:
                return self.playerContent(flag, self._fix(im.group(1)), vipFlags)
            mm = re.search(r'(https?://[^\s"\']+?\.(?:m3u8|mp4|flv)[^\s"\']*)', html, re.I)
            if mm:
                return {'parse': 0, 'playUrl': '', 'url': mm.group(1).replace('\\/', '/'), 'header': self._media_header(full)}
        ret['url'] = full
        ret['header'] = self._media_header(full)
        return ret

    def localProxy(self, params=None):
        return None