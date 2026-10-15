# -*- coding: utf-8 -*-
"""
================================================================================
 AnyShort 短劇 -- TVBox / CatVod Python 源 (繁體中文 / zh-Hant)
================================================================================
 站點:     https://anyshort.net   (AnyShort —— 多語言短劇平台)
 語言:     zh-Hant (繁體中文)，可在下方 LANG 改成 zh-Hans / en 等
 架構:     官方 REST API (nginx 同源代理 /v1)，無人機驗證 / 無 WAF，純 Python 可直連。

 【接口一覽 / 已在沙箱實測跑通】
   握手:   POST /v1/auth/session  -> access_token (Bearer)
   標籤:   GET  /v1/tags?lang=    -> 100 個題材(二級分類來源)
   瀏覽:   GET  /v1/browse?lang=&page=&sort=|source=  -> 全部 / 按來源
   搜索:   GET  /v1/search?q=&lang=&page=
   詳情:   GET  /v1/titles/{id}?lang=
   分集:   GET  /v1/titles/{id}/episodes?lang=
   播放:   GET  /v1/episodes/{eid}/play?lang= -> 簽名 CDN 直鏈 (mp4, 可 parse=0 秒播)

 【二級分類設計】
   首頁分類條 = 最新更新 + 熱門榜 + 三個來源(多語世界/繽紛萬象/時尚上頭)
              + 動態拉取的熱門中文題材(復仇/重生/豪門霸總/現代言情 …)。
   分類/搜索全部走 API，封面為 media.anyshort.net 直鏈(已確認可達)。

 【提速要點】
   1) requests.Session + 連接池復用 TCP/TLS，列表/詳情/播放多次請求不重復握手。
   2) 播放地址為簽名 mp4 直鏈，playerContent 返回 parse=0，跳過殼內二次解析，起播最快。
   3) 封面/數據皆官方 JSON，體積小、解析快。
   4) Token 僅握手一次並緩存，401 自動重握手。

 【合規提醒】僅供技術交流與個人學習。請遵守目標站點服務條款，控制請求頻率。
================================================================================
"""

import os
import re
import sys
import json
import time

try:
    import requests
    from requests.adapters import HTTPAdapter
    import urllib3
    urllib3.disable_warnings()
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ================================================================================
# 二、基類導入兼容 (TVBox / CatVod 殼約定)
# ================================================================================
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.append(_THIS_DIR)
if os.path.join(_THIS_DIR, '..') not in sys.path:
    sys.path.append(os.path.join(_THIS_DIR, '..'))

try:
    from base.spider import Spider
    _BASE_INFO = 'base.spider.Spider'
except ImportError:
    try:
        from base.spider import BaseSpider as Spider
        _BASE_INFO = 'base.spider.BaseSpider'
    except ImportError:
        try:
            from spider import Spider
            _BASE_INFO = 'spider.Spider'
        except ImportError:
            class _LocalStubSpider(object):
                """離線自測用的本地兜底基類。"""
                def fetch(self, url, headers=None, cookies=""):
                    return requests.get(url, headers=headers or {}, timeout=15, verify=False)
                def post(self, url, data, headers=None, cookies=None):
                    return requests.post(url, data=data, headers=headers or {}, timeout=15, verify=False)
                def postJson(self, url, json, headers=None, cookies=None):
                    return requests.post(url, json=json, headers=headers or {}, timeout=15, verify=False)
                def html(self, content):
                    return content
                def xpText(self, root, expr):
                    return ''
                def regStr(self, src, reg, group=1):
                    m = re.search(reg, src)
                    return m.group(group) if m else ''
                def str2json(self, s):
                    return json.loads(s)
                def cleanText(self, src):
                    return src
                def loadModule(self, name, fileName):
                    return None
                def getDependence(self):
                    return []
            Spider = _LocalStubSpider
            _BASE_INFO = 'LocalStub'


# ================================================================================
# 三、源主體
# ================================================================================
class Spider(Spider):

    # ----------------------------- 配置區 -----------------------------
    HOST = 'https://anyshort.net'
    API = 'https://anyshort.net/v1'        # nginx 同源代理的官方接口
    NAME = 'AnyShort短劇'
    LANG = 'zh-Hant'                       # 語言: zh-Hant / zh-Hans / en / ja ...

    # 三個來源(對應官網 kho 三個集合)
    SOURCES = [
        ('多語世界', 'pinedrama'),
        ('繽紛萬象', 'netshort'),
        ('時尚上頭', 'reelshort'),
    ]

    # 題材分類兜底(接口拉取失敗時使用)，格式 (tag_id, 顯示名)
    FALLBACK_TAGS = [
        (3, '上流社會'), (137, '復仇'), (215, '惡有惡報'), (8, '虐戀情深'),
        (329, '逆襲'), (330, '現代言情'), (133, '大女主'), (128, '爽文'),
        (334, '王者歸來'), (210, '劇情反轉'), (336, '甜寵戀愛'), (127, '治癒暖心'),
        (375, '豪門霸總'), (316, '重生'), (331, '奇幻戀愛'), (325, '追妻火葬場'),
        (252, '隱藏身分'), (201, '多重身分'), (208, '虐戀'),
    ]

    # 網絡參數
    TIMEOUT = 15
    RETRY = 1
    SLEEP_BASE = 0.3
    MAX_TAGS = 18                          # 動態題材分類上限

    _CJK = re.compile(r'[\u4e00-\u9fff]')  # 過濾非中文題材(避免緬甸/印尼等語)

    # ----------------------------- 生命周期 -----------------------------
    def init(self, extend=""):
        self.headers = {
            'User-Agent': ('Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'),
            'Accept': 'application/json',
            'Accept-Language': '%s,zh;q=0.9' % self.LANG,
            'Origin': self.HOST,
            'Referer': self.HOST + '/' + self.LANG + '/',
        }
        self.session = None
        self.token = None
        self.token_expire = 0
        if _HAS_REQUESTS:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
            adapter = HTTPAdapter(pool_connections=12, pool_maxsize=12, max_retries=0)
            self.session.mount('https://', adapter)
            self.session.mount('http://', adapter)
        self._classes = None                 # 分類緩存
        self._dbg('init done: base=%s | requests=%s | lang=%s' % (_BASE_INFO, _HAS_REQUESTS, self.LANG))

    def getName(self):
        return self.NAME

    def getDependence(self):
        return []

    def destroy(self):
        if getattr(self, 'session', None) is not None:
            try:
                self.session.close()
            except Exception:
                pass

    # ----------------------------- 工具方法 -----------------------------
    def _dbg(self, *msg):
        try:
            print('[%s] %s' % (self.NAME, ' '.join(str(m) for m in msg)))
        except Exception:
            pass

    def _ensure_token(self):
        """確保有有效 Bearer token；過期或缺失則握手。"""
        if self.token and time.time() < self.token_expire:
            return True
        if not _HAS_REQUESTS or self.session is None:
            return False
        try:
            r = self.session.post(self.API + '/auth/session',
                                  json={'platform': 'web'}, timeout=self.TIMEOUT, verify=False)
            if r.status_code != 200:
                self._dbg('handshake HTTP', r.status_code)
                return False
            j = r.json()
            self.token = j['data']['access_token']
            exp = j['data'].get('expires_in') or 3600
            self.token_expire = time.time() + max(60, int(exp) - 60)
            self.session.headers['Authorization'] = 'Bearer ' + self.token
            return True
        except Exception as e:
            self._dbg('handshake fail:', e)
            self.token = None
            return False

    def _api_get(self, path, params=None):
        """帶 Bearer 鑒權的 GET，401 自動重握手一次。返回解析後的 JSON(dict)。"""
        if not self._ensure_token():
            return {'data': [], 'page': {}}
        params = params or {}
        params.setdefault('lang', self.LANG)
        for _ in range(2):
            try:
                r = self.session.get(self.API + path, params=params,
                                     timeout=self.TIMEOUT, verify=False)
                if r.status_code == 401:
                    self.token = None
                    if self._ensure_token():
                        continue
                    return {'data': [], 'page': {}}
                if r.status_code != 200:
                    self._dbg('API %s HTTP %d' % (path, r.status_code))
                    return {'data': [], 'page': {}}
                return r.json()
            except Exception as e:
                self._dbg('API %s fail:' % path, e)
                return {'data': [], 'page': {}}
        return {'data': [], 'page': {}}

    @staticmethod
    def _as_list(j):
        """統一取出列表：data 為 list 直接用；為 dict 則取 list/items/titles。"""
        d = j.get('data')
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ('list', 'items', 'titles', 'rows', 'results'):
                if isinstance(d.get(k), list):
                    return d[k]
        return []

    def _page_meta(self, j, got, limit):
        """盡量從響應 page 元信息推算頁數；否則按是否取滿一頁估算。"""
        pg = j.get('page') or {}
        if isinstance(pg, dict) and pg.get('pages'):
            return pg.get('pages')
        if isinstance(pg, dict) and pg.get('has_more') is not None:
            return 9999 if pg.get('has_more') else 1
        return 9999 if len(got) >= limit else 1

    def _item_to_vod(self, it):
        """API 返回的影片條目 -> TVBox vod 字典。"""
        tid = it.get('title_id') or it.get('id')
        return {
            'vod_id': str(tid),
            'vod_name': it.get('name') or it.get('title') or '',
            'vod_pic': it.get('cover_url') or it.get('cover') or '',
            'vod_remarks': self._remarks(it),
        }

    @staticmethod
    def _remarks(it):
        ep = it.get('total_episodes') or it.get('episode_count')
        if ep:
            return '%d集' % ep
        vc = it.get('view_count')
        if vc:
            try:
                if vc >= 1e8:
                    return '%.1f億播' % (vc / 1e8)
                if vc >= 1e4:
                    return '%.1f萬播' % (vc / 1e4)
            except Exception:
                pass
        return ''

    # ----------------------------- 分類構建 -----------------------------
    def _fetch_tags(self):
        """動態拉取熱門中文題材，返回 [(id, name), ...]。"""
        j = self._api_get('/tags')
        tags = self._as_list(j)
        zh = [t for t in tags if self._CJK.search(t.get('name', ''))]
        zh.sort(key=lambda t: -(t.get('title_count') or 0))
        return [(t['tag_id'], t['name']) for t in zh[:self.MAX_TAGS]]

    def _build_classes(self):
        if self._classes is not None:
            return self._classes
        classes = [
            {'type_id': 'newest', 'type_name': '最新更新'},
            {'type_id': 'popular', 'type_name': '熱門榜'},
        ]
        for label, src in self.SOURCES:
            classes.append({'type_id': 'src:' + src, 'type_name': label})
        tags = self._fetch_tags()
        if not tags:
            tags = self.FALLBACK_TAGS
        for tid, name in tags:
            classes.append({'type_id': 'tag:%d' % tid, 'type_name': name})
        self._classes = classes
        self._dbg('分類數:', len(classes))
        return classes

    # ----------------------------- homeContent -----------------------------
    def homeContent(self, filter):
        return {'class': self._build_classes(), 'filters': {}}

    def homeVideoContent(self):
        j = self._api_get('/browse', {'page': 1, 'sort': 'newest', 'limit': 24})
        items = self._as_list(j)
        return {'list': [self._item_to_vod(it) for it in items], 'page': 1,
                'pagecount': 9999, 'limit': 24, 'total': len(items)}

    # ----------------------------- categoryContent -----------------------------
    def categoryContent(self, tid, pg, filter, extend):
        pg = max(1, int(pg) if str(pg).isdigit() else 1)
        if tid in ('newest', 'popular'):
            j = self._api_get('/browse', {'page': pg, 'sort': tid})
        elif tid.startswith('src:'):
            j = self._api_get('/browse', {'page': pg, 'source': tid.split(':', 1)[1]})
        elif tid.startswith('tag:'):
            j = self._api_get('/tags/%s/titles' % tid.split(':', 1)[1], {'page': pg})
        else:
            j = self._api_get('/browse', {'page': pg, 'sort': 'newest'})
        items = self._as_list(j)
        limit = (j.get('page') or {}).get('limit') or 18
        total = (j.get('page') or {}).get('total')
        pagecount = self._page_meta(j, items, limit)
        return {
            'list': [self._item_to_vod(it) for it in items],
            'page': pg, 'pagecount': pagecount, 'limit': limit,
            'total': total if total else len(items),
        }

    # ----------------------------- detailContent -----------------------------
    def detailContent(self, ids):
        result = {'list': []}
        if not ids:
            return result
        tid = str(ids[0]).strip()
        d = self._api_get('/titles/%s' % tid).get('data') or {}
        eps_j = self._api_get('/titles/%s/episodes' % tid)
        eps = self._as_list(eps_j)
        # 優先選可播放且未鎖定的集；若全鎖則退而求其次全部納入
        playable = [e for e in eps if e.get('has_streams') and not e.get('locked')]
        if not playable:
            playable = eps

        vod = {
            'vod_id': tid,
            'vod_name': d.get('name') or '',
            'vod_pic': d.get('cover_url') or d.get('cover') or '',
            'vod_content': (d.get('description') or '').strip(),
            'vod_remarks': self._remarks(d),
            'vod_year': '',
            'type_name': ' / '.join(t.get('name', '') for t in d.get('tags', [])[:3]),
            'vod_play_from': 'AnyShort',
            'vod_play_url': '',
        }

        play_pairs = []
        for e in sorted(playable, key=lambda x: (x.get('episode_no') or 0)):
            eid = e.get('episode_id')
            no = e.get('episode_no') or (len(play_pairs) + 1)
            if eid:
                play_pairs.append('%s$%s' % (no, eid))
        vod['vod_play_url'] = '#'.join(play_pairs)
        if not vod['vod_play_url']:
            vod['vod_remarks'] = (vod['vod_remarks'] + ' 需付費/暫無免費源' if vod['vod_remarks'] else '需付費/暫無免費源')
        self._dbg('detail %s: 集數=%d' % (tid, len(play_pairs)))
        result['list'].append(vod)
        return result

    # ----------------------------- playerContent -----------------------------
    def playerContent(self, flag, id, vipFlags=''):
        eid = str(id).strip()
        j = self._api_get('/episodes/%s/play' % eid)
        d = j.get('data') or {}
        url = (d.get('selected') or {}).get('url')
        streams = d.get('streams') or []
        if not url and streams:
            # 選最高畫質
            def _q(s):
                m = re.search(r'(\d+)', str(s.get('quality') or ''))
                return int(m.group(1)) if m else 0
            url = sorted(streams, key=_q)[-1].get('url')
        if not url:
            self._dbg('play %s 未取得地址' % eid)
            return {'parse': 0, 'url': '', 'header': {}}
        header = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.HOST + '/' + self.LANG + '/',
            'Origin': self.HOST,
        }
        # 直鏈 mp4 跳過二次解析(parse=0)；m3u8 交給殼內解析(parse=1)
        parse = 0 if '.m3u8' not in url else 1
        self._dbg('play %s -> %s (parse=%d)' % (eid, url[:60], parse))
        return {'parse': parse, 'url': url, 'jx': 0, 'header': header}

    # ----------------------------- searchContent -----------------------------
    def searchContent(self, key, quick='', pg=1):
        pg = max(1, int(pg) if str(pg).isdigit() else 1)
        j = self._api_get('/search', {'q': key, 'page': pg})
        items = self._as_list(j)
        has_more = (j.get('page') or {}).get('has_more')
        pagecount = 9999 if has_more else pg
        return {
            'list': [self._item_to_vod(it) for it in items],
            'page': pg, 'pagecount': pagecount, 'limit': 20, 'total': len(items),
        }

    def searchContentPage(self, key, quick='', page='1'):
        return self.searchContent(key, quick, int(page) if str(page).isdigit() else 1)

    # ----------------------------- 可選方法 -----------------------------
    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False


# ================================================================================
# 本地自檢
# ================================================================================
if __name__ == '__main__':
    print('=' * 60)
    print('AnyShort 短劇 TVBox Python 源 - 本地自檢')
    print('=' * 60)
    print('base      :', _BASE_INFO)
    print('requests  :', _HAS_REQUESTS)
    print('-')

    s = Spider()
    s.init('')

    required = ['init', 'getName', 'homeContent', 'categoryContent',
                'detailContent', 'playerContent', 'searchContent']
    for m in required:
        print('method %-18s %s' % (m, 'OK' if hasattr(s, m) else 'MISSING!'))

    print('-')
    hc = s.homeContent(False)
    print('分類數:', len(hc.get('class', [])))
    for c in hc.get('class', [])[:12]:
        print('  %-12s -> %s' % (c['type_name'], c['type_id']))

    print('-')
    print('===== homeVideoContent (最新) =====')
    r = s.homeVideoContent()
    print('本頁=%d' % len(r['list']))
    if r['list']:
        print('第一條:', r['list'][0]['vod_name'], '|', r['list'][0]['vod_pic'][:50])

    print('-')
    print('===== categoryContent (熱門榜 page1) =====')
    r = s.categoryContent('popular', '1', {}, {})
    print('本頁=%d' % len(r['list']))
    if r['list']:
        print('第一條:', r['list'][0]['vod_name'])

    print('-')
    print('===== searchContent (總裁) =====')
    r = s.searchContent('總裁', '', 1)
    print('本頁=%d' % len(r['list']))
    if r['list']:
        print('第一條:', r['list'][0]['vod_name'])

    print('-')
    print('===== detailContent + playerContent 聯調 =====')
    if r['list']:
        vid = r['list'][0]['vod_id']
        d = s.detailContent([vid])
        if d['list']:
            v = d['list'][0]
            print('劇名:', v['vod_name'], '| 集數:', v['vod_play_url'].count('#') + (1 if v['vod_play_url'] else 0))
            print('封面:', v['vod_pic'][:50])
            if v['vod_play_url']:
                eid = v['vod_play_url'].split('$')[1].split('#')[0]
                p = s.playerContent('AnyShort', eid)
                print('播放 parse=%d url=%s' % (p.get('parse'), (p.get('url') or '')[:70]))
        else:
            print('detailContent 返回空')
    print('=' * 60)
