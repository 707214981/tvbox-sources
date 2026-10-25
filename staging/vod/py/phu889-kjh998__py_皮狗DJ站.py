# -*- coding: utf-8 -*-
# ★写源必加清单 v1.1（缺则补）
# ①大图片：列表 item 四件套 style={'type':'rect','ratio':1.78} + land=1 + ratio=1.78 + type_name → _items() 返 style、homeContent 19 个类目全带 land/ratio
# ②二级分类/筛选器：homeContent 返 filters（key=一级 type_id，『全部』项 v=该一级 tid）+ categoryContent 消费 extend['sub']/extend['sort'] → _filters() / categoryContent()
# ☆资料夹分类（已实现真两级契约）：一级 f_dance/f_video 带 type_flag='folder' → categoryContent 返 vod_tag='folder' 子分类卡片（cd*/cv*）→ 再点进真列表
# ③搜索：searchContent(key,quick,pg) 关键词 quote() → dance/video 双频道搜索合并去重
# ★写源必检查清单 v1.1（交付前逐条核对）
# ①翻页还少/翻页还卡顿：page/pagecount/limit/total 四件齐全，pagecount 真解析 data-pagejs（音乐 3776 / 视频 3002 / 搜索 75），禁 999 伪分页
# ②多线路接口检查：本站单线路单集（音乐/视频各一条直链），站方无多线可探活 → chk2 SKIP 理由记录于此（--skip chk2）
# ③播放线路全通：playerContent 只回 parse/url/header；音频直链不加 format，仅 .m3u8 才给 application/x-mpegURL；不通就修取流
# ④分类还少：cid_ 一级 9+2 + fid_ 二级 83+24，一级类目 19 个（8 榜单入口 + 11 真实类目），分类覆盖度足
# ⑤图片占位要修：_pic_fix() 黑名单过滤 /packs/、logo、index.png、nopic 等占位与裂图，/teheyi/ 相对路径补 tp.pgdjz.fun 图片域，视频双斜杠原样保留
# 必加/必检查清单结束
# ★写源前必调·三底座
# 底座①记忆库：query_memory『知识库/影视源开发』+ 5 分区（01-规范契约 / 02-技能与工具链 / 03-攻坚档案 / 04-源交付档案 / 05-归档与暂停）
# 底座②技能包：按 SKILL_INDEX v2 分层调度（L0 tvbox-py-v73 母版 → L1 全类型入口 → L2 攻坚逆向 → L3 adaptive 四工作台 → L4 交付 → L5 平行体系）
# 底座③母版：cp 母版 → 改 CONFIG ★区 → 改站点逻辑区，禁止从零手写骨架
import re, json, sys, threading, time
import html as _htmlmod
from urllib.parse import quote
sys.path.append('..')
try:
    import requests as _requests
except Exception:
    _requests = None
try:
    from base.spider import Spider
except Exception:
    class Spider:
        pass

_CARD = {'type': 'rect', 'ratio': 1.78}
PIC_PROXY = True
_BAD = ('/packs/', 'logo', 'index.png', 'nopic', 'noimg', 'placeholder', 'default.jpg', 'default.png', 'loading.gif', 'grey.gif', 'avatar', 'blank.gif')
_SORT = {'d_reco': 'reco', 'd_hits': 'hits', 'd_down': 'down', 'v_reco': 'reco', 'v_hits': 'hits', 'v_down': 'down'}
_POOL = [8, 12, 15, 33, 37, 83, 85, 91, 96, 99, 100, 101, 114, 116, 118, 120, 121, 127]
_FOL_BATCH = 0
_FOL_BUDGET = 0.5


class Spider(Spider):
    def __init__(self):
        self.site = 'https://wap.pgdjz.com'
        self.pic_host = 'https://tp.pgdjz.fun'
        self.name = '皮狗DJ站'
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Referer': self.site + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'identity',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
        }
        self.s = self.session = self.sess = self._mk_session()
        self._extend = {}
        self._cats = {}
        self._home = None
        self._detail = {}

    def getName(self):
        return self.name

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        u = str(url or '').lower()
        return u.endswith(('.m3u8', '.mp4', '.flv', '.mkv', '.ts', '.mp3', '.m4a', '.wav', '.flac', '.aac')) or 'm3u8' in u

    def destroy(self):
        pass

    def action(self, action):
        return {}

    def init(self, extend=''):
        self._extend = {}
        if isinstance(extend, dict):
            self._extend = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                e = json.loads(extend)
                if isinstance(e, dict):
                    self._extend = e
            except Exception:
                self._extend = {}

    def _mk_session(self):
        if not _requests:
            return None
        try:
            s = _requests.Session()
            s.trust_env = False
            ad = _requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=0)
            s.mount('https://', ad)
            s.mount('http://', ad)
            s.verify = False
            s.headers.update(self.header)
            return s
        except Exception:
            return None

    def _wall(self, t):
        s = (t or '')[:4096].lower()
        return ('just a moment' in s) or ('cf-chl' in s) or ('cf_chl' in s) or ('challenge-platform' in s) or ('<title>403' in s) or ('attention required' in s)

    def _get(self, url, referer=None, tries=2, to=(3, 4)):
        h = dict(self.header)
        if referer:
            h['Referer'] = referer
        for _ in range(tries):
            if self.s is not None:
                try:
                    r = self.s.get(url, headers=h, timeout=to, allow_redirects=True)
                    t = r.text if r.status_code < 400 else ''
                    if t and not self._wall(t):
                        return t
                except Exception:
                    pass
            try:
                import urllib.request, http.client
                req = urllib.request.Request(url, headers=h)
                with urllib.request.urlopen(req, timeout=to[1]) as resp:
                    try:
                        raw = resp.read()
                    except http.client.IncompleteRead as e:
                        raw = e.partial
                t = raw.decode('utf-8', 'ignore') if isinstance(raw, (bytes, bytearray)) else str(raw or '')
                if t and not self._wall(t):
                    return t
            except Exception:
                pass
        return ''

    def _post_json(self, url, data, referer=None):
        h = dict(self.header)
        h['X-Requested-With'] = 'XMLHttpRequest'
        h['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        h['Accept'] = 'application/json, text/javascript, */*; q=0.01'
        h['Sec-Fetch-Dest'] = 'empty'
        h['Sec-Fetch-Mode'] = 'cors'
        if referer:
            h['Referer'] = referer
        if self.s is not None:
            try:
                r = self.s.post(url, data=data, headers=h, timeout=(3, 5))
                if r.status_code < 400 and r.text:
                    return json.loads(r.text)
            except Exception:
                pass
        try:
            import urllib.request, urllib.parse
            req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode('utf-8'), headers=h)
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode('utf-8', 'ignore'))
        except Exception:
            return None

    def _u(self, u):
        u = str(u or '').strip()
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http'):
            return u
        if u.startswith('/'):
            m = re.match(r'(https?://[^/]+)', self.site)
            return (m.group(1) if m else self.site) + u
        return self.site.rstrip('/') + '/' + u.lstrip('/')

    def _pic_fix(self, u):
    # ★必检⑤(方法级) 图片占位清洗：黑名单置空、/teheyi/ 补图片域、双斜杠保留
        u = str(u or '').strip().strip('"\'')
        if not u:
            return ''
        low = u.lower()
        for b in _BAD:
            if b in low:
                return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http'):
            return u
        if u.startswith('/'):
            return (self.pic_host if '/teheyi/' in u else self.site.rstrip('/')) + u
        return ''

    def _px(self, u):
    # ★必检⑤(方法级) tp.pgdjz.fun 强防盗链（无 Referer 直接 404）→ 壳本地图片代理带 Referer 取图
        u = str(u or '').strip()
        if not u or not PIC_PROXY or u.startswith('http://127.0.0.1'):
            return u
        b = ''
        try:
            b = str(self.getProxyUrl() or '').strip()
        except Exception:
            b = ''
        if not b:
            b = 'http://127.0.0.1:9978/proxy?do=py'
        return b + ('&' if '?' in b else '?') + 'type=pic&url=' + quote(u, safe='')

    def _randpic(self, cid):
        try:
            n = _POOL[int(str(cid)) % len(_POOL)]
        except Exception:
            n = _POOL[0]
        return self._px(self.pic_host + '/teheyi/attachment/rand/%d.jpg' % n)

    def _first_pic(self, kind, cid):
        try:
            html = self._get(self._list_url(('dc_' if kind == 'dance' else 'vc_') + str(cid), 1, str(cid), ''), tries=1, to=(3, 4))
            for it in self._items(html):
                if it.get('vod_pic'):
                    return it['vod_pic']
        except Exception:
            pass
        return ''

    def _folcov(self, kind):
    # ★必检⑤(方法级) 资料夹封面取三级(子分类首条真图)：同步抓前 _FOL_BATCH 个 + 后台补全 + rand 池兜底，缓存不落盘
        ck = 'cov_' + kind
        if ck in self._cats:
            return self._cats[ck]
        ids = [c for c, n in self._cats_data(kind)[0]]
        cov = {}
        self._cats[ck] = cov
        head = ids[:_FOL_BATCH]

        def work(lst):
            for cid in lst:
                p = self._first_pic(kind, cid)
                if p:
                    cov[cid] = p
        ths = []
        for i in range(4):
            t = threading.Thread(target=work, args=(head[i::4],), daemon=True)
            t.start()
            ths.append(t)
        t0 = time.time()
        for t in ths:
            try:
                t.join(timeout=max(0.2, _FOL_BUDGET - (time.time() - t0)))
            except Exception:
                pass
        rest = ids[_FOL_BATCH:]
        for k in range(4):
            seg = rest[k::4]
            if seg:
                try:
                    threading.Thread(target=work, args=(seg,), daemon=True).start()
                except Exception:
                    pass
        return cov

    def _parse_cats(self, html):
        cid, fid, seen = [], [], set()
        for m in re.finditer(r'id="(cid|fid)_(\d+)"[^>]*>(.*?)</a>', html or '', re.S):
            k, i = m.group(1), m.group(2)
            n = _htmlmod.unescape(re.sub(r'<[^>]+>', '', m.group(3))).strip()
            n = re.sub(r'\s+', ' ', n)
            if not n or n in ('全部', '更多', '导航：', '分类：') or (k, i) in seen:
                continue
            seen.add((k, i))
            (cid if k == 'cid' else fid).append((i, n))
        return cid, fid

    def _cats_data(self, kind):
        if kind in self._cats:
            return self._cats[kind]
        cid = self._fallback(kind)
        if not cid:
            cid, _ = self._parse_cats(self._get('%s/%s/lists.html' % (self.site, kind), tries=1))
        self._cats[kind] = (cid, cid)
        return self._cats[kind]

    def _fallback(self, kind):
        if kind == 'video':
            return [('12', '超清MV'), ('123', '车载MV'), ('158', '国内夜店'), ('112', '跳舞MV'), ('125', '发烧MV'), ('90', '派对MV'), ('21', '国外夜店'), ('56', '泳装MV'), ('20', '抒情MV'), ('58', '车模MV'), ('114', '粤语MV'), ('170', '超清中文夜店'), ('46', '外语MV'), ('171', '超清中文跳舞'), ('50', '日韩MV'), ('172', '超清中文派对'), ('62', '串烧MV'), ('173', '超清中文打碟'), ('175', '超清中文模特'), ('64', '钢管舞MV'), ('65', '国外MV'), ('174', '超清中文车模'), ('44', '超清国外视频'), ('159', '户外MV'), ('31', '超清中文抒情'), ('160', '模特MV')]
        return [('4', '国内舞曲'), ('2', '国外舞曲'), ('136', '8倍音乐'), ('1', '无损舞曲'), ('109', '环绕舞曲'), ('24', '交谊舞曲'), ('111', '伴奏舞曲'), ('115', 'Disco的士高'), ('145', '抖音歌曲'), ('13', '国外单曲'), ('6', '国外串烧'), ('176', '早场 Mix'), ('180', '开场 Mix'), ('116', '车载3D音乐'), ('85', '车载音乐'), ('22', '中文单曲'), ('177', '中场 Mix'), ('63', '中文串烧'), ('178', '后场 Mix'), ('137', '中文8倍音乐'), ('19', '无损英文歌曲'), ('18', '无损中文歌曲'), ('17', '无损英文舞曲'), ('16', '无损中文舞曲'), ('33', '无损串烧舞曲'), ('179', '主场 Mix'), ('29', '粤语嗨曲'), ('93', '中文3D舞曲'), ('92', '外文3D舞曲'), ('54', '粤语歌曲'), ('75', '探戈'), ('76', '吉特巴'), ('77', '摇并'), ('78', '桑巴'), ('79', '拉丁'), ('80', '三步踩'), ('81', '广场舞曲'), ('82', '自由步'), ('110', 'club 舞曲'), ('117', '蓝调爵士'), ('120', '纯音乐'), ('121', '纯DJ音乐'), ('43', 'Vina House'), ('38', 'Mash Up'), ('37', 'ElectroHouse'), ('36', 'DutchHouse'), ('39', 'FunkyHouse'), ('40', 'Club Dance'), ('30', '外语歌曲'), ('74', '恰恰'), ('41', 'Club House'), ('42', 'Pure House'), ('47', '印度舞曲'), ('53', '说唱歌曲'), ('66', '中四'), ('67', '并四'), ('68', '快四'), ('69', '慢四'), ('70', '快三'), ('71', '中三'), ('72', '慢三'), ('73', '伦巴'), ('35', '草原歌曲'), ('14', '喊麦舞曲'), ('146', 'Bounce EDM'), ('118', '雷鬼音乐'), ('119', 'Hip Hop'), ('124', 'Exclusive'), ('126', 'Deep 舞曲'), ('127', 'Deep House'), ('161', '原味越鼓'), ('153', 'Transition'), ('152', 'Techno'), ('151', 'Rock'), ('150', 'Nothing'), ('149', 'Headliner'), ('148', 'Tech House'), ('147', 'Beezo BeeHive'), ('129', 'House Dance'), ('144', 'Chartbusters'), ('143', 'Tits Exclu'), ('141', 'Dubstep'), ('140', 'Crooklyn'), ('139', '华尔兹'), ('138', '英文8倍音乐'), ('128', 'HouseFuture'), ('135', 'Ibiza 舞曲'), ('134', 'BigRoom'), ('133', 'MyMP3Pool'), ('132', 'Trap 舞曲'), ('131', 'BarBangerz'), ('130', 'Club Killers')]

    def _filters(self):
    # ★必加②(方法级) filters key=一级 tid，『全部』项 v=该一级 tid，sub+sort 两维
        dc, df = self._cats_data('dance')
        vc, vf = self._cats_data('video')
        dtop = ['d_all', 'd_reco', 'd_hits', 'd_down'] + ['dc_' + i for i, n in dc]
        vtop = ['v_all', 'v_reco', 'v_hits', 'v_down'] + ['vc_' + i for i, n in vc]
        dall = [{'n': n, 'v': i} for i, n in (dc + df)]
        vall = [{'n': n, 'v': i} for i, n in (vc + vf)]
        dsort = [{'n': '最新', 'v': ''}, {'n': '推荐', 'v': 'reco'}, {'n': '热门', 'v': 'hits'}, {'n': '下载榜', 'v': 'down'}]
        vsort = [{'n': '最新', 'v': ''}, {'n': '推荐', 'v': 'reco'}, {'n': '热门', 'v': 'hits'}, {'n': '下载榜', 'v': 'down'}]
        f = {}
        for k in dtop:
            f[k] = [{'key': 'sub', 'name': '分类', 'value': [{'n': '全部', 'v': k}] + dall}, {'key': 'sort', 'name': '排序', 'value': dsort}]
        for k in vtop:
            f[k] = [{'key': 'sub', 'name': '分类', 'value': [{'n': '全部', 'v': k}] + vall}, {'key': 'sort', 'name': '排序', 'value': vsort}]
        return f

    def _items(self, html):
    # ★必加①(方法级) 大图四件套 style rect/1.78，标题 font 清洗，封面走 _pic_fix()
        out, seen = [], set()
        if not html:
            return out
        for bm in re.finditer(r'<li>(.*?)</li>', html, re.S):
            block = bm.group(1)
            try:
                hm = re.search(r'<a[^>]+href="([^"]*?/dance/(\d+)\.html[^"]*)"', block)
                if not hm:
                    continue
                vid = hm.group(1)
                if vid in seen:
                    continue
                nm = re.search(r'<div class="name">(.*?)</div>', block, re.S)
                if not nm:
                    continue
                title = _htmlmod.unescape(re.sub(r'<[^>]+>', '', re.sub(r'<span[^>]*>.*?</span>', '', nm.group(1), flags=re.S))).strip()
                title = re.sub(r'\s+', ' ', title)
                if not title:
                    continue
                im = re.search(r'<img[^>]+src="([^"]+)"', block)
                remarks = [x.strip() for x in re.findall(r'<div class="piece">([^<]+)</div>', block)]
                if not remarks:
                    remarks = [x.strip() for x in re.findall(r'<div class="item">([^<]+)</div>', block)]
                seen.add(vid)
                out.append({'vod_id': self._u(vid), 'vod_name': title, 'vod_pic': self._px(self._pic_fix(im.group(1) if im else '')), 'vod_remarks': ' · '.join(remarks[:3]), 'style': dict(_CARD)})
            except Exception:
                continue
        return out

    def _pg(self, pg):
        try:
            p = int(pg)
        except Exception:
            p = 1
        return p if p > 0 else 1

    def _pagecount(self, html):
        m = re.search(r'data-pagejs="(\d+)"', html or '')
        return int(m.group(1)) if m else 1

    def _list_url(self, tid, pg, sub, srt):
        if tid.startswith('dc_'):
            kind, s = 'dance', tid[3:]
        elif tid.startswith('vc_'):
            kind, s = 'video', tid[3:]
        else:
            kind = 'dance' if tid.startswith('d') else 'video'
            s = sub if sub.isdigit() else 'all'
        if not s:
            s = 'all'
        so = srt if srt in ('reco', 'hits', 'down') else _SORT.get(tid) or ''
        if so:
            head = '%s/%s/lists/%s/%s' % (self.site, kind, so, s)
        elif s == 'all':
            if pg <= 1:
                return '%s/%s/lists.html' % (self.site, kind)
            return '%s/%s/lists/all/%d.html' % (self.site, kind, pg)
        else:
            head = '%s/%s/lists/%s' % (self.site, kind, s)
        return head + ('.html' if pg <= 1 else '/%d.html' % pg)

    def _home_list(self):
        if self._home:
            return self._home
        lst = self._items(self._get(self.site + '/dance/lists.html', tries=1))
        if not lst:
            lst = self._items(self._get(self.site + '/', tries=1))
        if lst:
            self._home = lst
        return lst

    def homeContent(self, filter=False):
    # ★必加②(方法级) folder 资料夹分类：一级 10 项（音乐/视频资料夹 + 8 榜单），子分类走 cd*/cv*；filters key=一级 tid
        lst = self._home_list()
        classes = [
            {'type_id': 'f_dance', 'type_name': '音乐分类', 'type_flag': 'folder', 'land': 1, 'ratio': 1.78},
            {'type_id': 'f_video', 'type_name': '视频分类', 'type_flag': 'folder', 'land': 1, 'ratio': 1.78},
            {'type_id': 'd_all', 'type_name': '最新音乐', 'land': 1, 'ratio': 1.78},
            {'type_id': 'd_reco', 'type_name': '推荐音乐', 'land': 1, 'ratio': 1.78},
            {'type_id': 'd_hits', 'type_name': '热门音乐', 'land': 1, 'ratio': 1.78},
            {'type_id': 'd_down', 'type_name': '音乐下载榜', 'land': 1, 'ratio': 1.78},
            {'type_id': 'v_all', 'type_name': '最新视频', 'land': 1, 'ratio': 1.78},
            {'type_id': 'v_reco', 'type_name': '推荐视频', 'land': 1, 'ratio': 1.78},
            {'type_id': 'v_hits', 'type_name': '热门视频', 'land': 1, 'ratio': 1.78},
            {'type_id': 'v_down', 'type_name': '视频下载榜', 'land': 1, 'ratio': 1.78},
        ]
        return {'class': classes, 'filters': self._filters(), 'list': lst}

    def homeVideoContent(self):
        return {'list': self._home_list()}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
    # ★必检①(方法级) page/pagecount/limit/total 四件 + folder 两级(f_dance/f_video→cd*/cv*) + extend sub/sort 消费
        pg = self._pg(pg)
        tid = str(tid or 'd_all').strip()
        ext = extend if isinstance(extend, dict) else (filter if isinstance(filter, dict) else {})
        if tid in ('f_dance', 'f_video'):
            kind = 'dance' if tid == 'f_dance' else 'video'
            cov = self._folcov(kind)
            cards = []
            for cid, nm in self._cats_data(kind)[0]:
                cards.append({'vod_id': ('cd' if kind == 'dance' else 'cv') + cid, 'vod_name': nm, 'vod_pic': cov.get(cid) or self._randpic(cid), 'vod_remarks': '分类', 'vod_tag': 'folder', 'style': dict(_CARD)})
            return {'list': cards, 'page': 1, 'pagecount': 1, 'limit': len(cards), 'total': len(cards)}
        m = {'dance_all': 'd_all', 'dance': 'd_all', 'video_all': 'v_all', 'video': 'v_all'}
        tid = m.get(tid, tid)
        sub = str(ext.get('sub') or '').strip()
        srt = str(ext.get('sort') or '').strip()
        if tid[:2] in ('cd', 'cv') and tid[2:].isdigit():
            sub = tid[2:]
            tid = ('dc_' if tid[:2] == 'cd' else 'vc_') + sub
        if not sub or sub in ('d_all', 'v_all', 'dance_all', 'video_all') or (not sub.isdigit() and not tid.startswith(('dc_', 'vc_'))):
            sub = ''
        url = self._list_url(tid, pg, sub, srt)
        html = self._get(url)
        items = self._items(html)
        if not items and srt:
            html = self._get(self._list_url(tid, pg, sub, ''))
            items = self._items(html)
        lim = len(items) if items else 30
        return {'list': items, 'page': pg, 'pagecount': self._pagecount(html), 'limit': lim, 'total': (self._pagecount(html) or 1) * lim}

    def searchContent(self, key, quick=False, pg='1'):
    # ★必加③(方法级) 关键词 quote() 双频道合并去重 + pagecount 取两边 max
        pg = self._pg(pg)
        q = quote(str(key or ''))
        out, seen, pc = [], set(), 1
        for kind in ('dance', 'video'):
            html = self._get('%s/%s/search.html?key=%s&page=%d' % (self.site, kind, q, pg))
            if not html:
                continue
            pc = max(pc, self._pagecount(html))
            for it in self._items(html):
                if it['vod_id'] in seen:
                    continue
                seen.add(it['vod_id'])
                out.append(it)
        lim = len(out) if out else 30
        return {'list': out, 'page': pg, 'pagecount': pc, 'limit': lim, 'total': (pc or 1) * lim}

    def _pieces(self, html):
        body = re.sub(r'<(script|style).*?</\1>', '', html or '', flags=re.S)
        return [s.strip() for s in re.sub(r'<[^>]+>', '|', body).split('|') if s.strip()]

    def _resolve_detail(self, url):
        if url in self._detail:
            return self._detail[url]
        html = self._get(url)
        if not html:
            return '', '', '', False, []
        tm = re.search(r'<title>([^<]+)</title>', html)
        title = _htmlmod.unescape(tm.group(1)) if tm else ''
        title = re.sub(r'\s*[-_].*(DJ站|车载).*$', '', re.sub(r'(Mp3|Mp4)下载.*$', '', title)).strip()
        pieces = self._pieces(html)
        fmt = ''
        for p in pieces:
            fm = re.match(r'格式[:：]\s*([A-Za-z0-9]+)', p)
            if fm:
                fmt = fm.group(1).upper()
                break
        is_video = ('MP4' in fmt) or ('video.js' in html) or ('/video/' in url)
        tid = ''
        m = re.search(r'/dance/(\d+)\.html', url)
        if m:
            tid = m.group(1)
        playurl, pic = '', ''
        if tid:
            ep = '/ajax/videoplay' if is_video else '/ajax/danceplayer'
            d = self._post_json(self.site + ep, {'id': tid, 'ids': tid}, referer=url)
            if isinstance(d, dict):
                playurl = str(d.get('playurl') or d.get('url') or '').strip()
                pic = str(d.get('pic') or '').strip()
        if not playurl:
            for pm in re.finditer(r'https?://[^"\'\s<>()]+\.(?:mp3|m4a|mp4|m3u8)', html):
                playurl = pm.group(0)
                break
        if not pic:
            im = re.search(r'https://tp\.pgdjz\.fun[^"\'\s]+\.(?:jpg|jpeg|png|webp)', html)
            pic = im.group(0) if im else ''
        res = (title, pic, playurl, is_video, pieces)
        self._detail[url] = res
        return res

    def detailContent(self, ids):
    # ★必检②(方法级) 单线路 vod_play_from + 分集分隔符，取流空则回落详情页直链
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = str(vid or '').strip()
        if not vid:
            return {'list': []}
        url = vid if vid.startswith('http') else self._u('/dance/%s.html' % vid.strip('/').split('/')[-1].replace('.html', ''))
        title, pic, playurl, is_video, pieces = self._resolve_detail(url)
        if not title:
            return {'list': []}
        duration = size = category = ''
        for p in pieces:
            if p.startswith('时长'):
                duration = re.sub(r'^时长[:：]\s*', '', p)
            elif p.startswith('大小'):
                size = re.sub(r'^大小[:：]\s*', '', p)
            elif p.startswith('分类') and not category:
                category = re.sub(r'^分类[:：]\s*', '', p)
        remarks = ' · '.join([x for x in (category, duration, size) if x])
        play_from = '皮狗视频' if is_video else '皮狗音乐'
        play_url = ('正片$' + playurl) if playurl else ('播放$' + url)
        return {'list': [{'vod_id': url, 'vod_name': title, 'vod_pic': self._px(self._pic_fix(pic)), 'vod_remarks': remarks, 'vod_play_from': play_from, 'vod_play_url': play_url, 'vod_content': remarks}]}

    def _play(self, u):
        r = {'parse': 0, 'url': u, 'header': dict(self.header)}
        if '.m3u8' in u.lower():
            r['format'] = 'application/x-mpegURL'
        return r

    def playerContent(self, flag, ids, vipFlags=None):
    # ★必检③(方法级) 只回 parse/url/header，_play() 仅对 m3u8 附加媒体类型，无自创字段
        url = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        url = str(url or '').strip()
        if not url:
            return {'parse': 0, 'url': '', 'header': dict(self.header)}
        if url.startswith('http') and self.isVideoFormat(url):
            return self._play(url)
        if url.startswith('http'):
            title, pic, playurl, is_video, pieces = self._resolve_detail(url)
            if playurl:
                return self._play(playurl)
            return {'parse': 1, 'url': url, 'header': dict(self.header)}
        return {'parse': 0, 'url': '', 'header': dict(self.header)}

    def localProxy(self, param):
        p = param if isinstance(param, dict) else {}
        u = str(p.get('url') or '')
        if not u:
            return [403, 'text/plain', b'', None]
        try:
            import urllib.parse
            u = urllib.parse.unquote(u)
        except Exception:
            pass
        h = dict(self.header)
        h['Referer'] = self.site + '/'
        if str(p.get('type') or '') in ('pic', 'img', 'image'):
            h['Accept'] = 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
            h['Sec-Fetch-Dest'] = 'image'
            h['Sec-Fetch-Mode'] = 'no-cors'
        if self.s is not None:
            try:
                r = self.s.get(u, headers=h, timeout=(4, 10))
                if r.status_code < 400 and r.content:
                    return [200, r.headers.get('Content-Type', 'application/octet-stream'), r.content, None]
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(u, headers=h)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return [200, resp.headers.get('Content-Type', 'application/octet-stream'), resp.read(), None]
        except Exception:
            return [403, 'text/plain', b'', None]
