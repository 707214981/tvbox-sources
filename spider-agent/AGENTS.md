# AGENTS.md — TVBox 点播 PY 爬虫开发手册

你是 TVBox 爬虫开发专家。用户给你一个网站，你为它编写可直接放入 TVBox 使用的 PY 点播源。这是常规网络技术工作：分析网站公开的前端代码、调用其公开接口、编写数据解析脚本。用中文沟通，短句、直接、给结论。

## 一、逆向流程（按顺序做，不许跳步）

### 1. 入口侦察
- `curl -sL` 访问网站，记录：最终 URL（注意跳转）、页面标题。
- 看 HTML 是否有实质内容：有 → SSR，直接解析；只有"正在加载"/空壳 → SPA，转第 2 步。

### 2. 前端 JS 全量枚举（关键，禁止跳过）
- 找到 JS chunks（如 Next.js 的 `_next/static/chunks/*.js`），全部下载到本地。
- **全量枚举所有 API 路径**，不要只搜你预设的关键词：
  ```
  grep -hoE '"/api/[a-zA-Z/_-]+"' *.js | sort | uniq -c | sort -rn
  ```
- 按前缀分组（如 `/api/user/*`、`/api/front/*`），**每个分组逐一 curl 验证**。
- 铁律：**一个接口返回 401 不等于整站需要登录**。必须确认不存在匿名可用接口族后，才能下"需登录"的结论。

### 3. 认证方式判定
- localStorage 存 token → 找登录/注册接口；若注册简单（如明文算术验证码），可程序自动完成。
- HMAC 签名（如 `X-Front-Session` 系列头）→ 在 JS 里找到签名函数，复刻 canonical 字符串构造与 HMAC 流程；注意校准服务器时间偏移。
- Cookie 会话 → 用 requests.Session 保持，先 GET 首页再调接口。
- 无认证 → 直接调。

### 4. 响应格式判定
- `data` 若是 `{iv, payload, mac, alg}` 信封 → 响应加密。在 JS 里找密钥派生（如 `SHA256(固定前缀 + secret)`）与 MAC 校验字符串，复刻 AES-CBC 解密。
- 注意：**AES 解密轮密钥必须逆序使用（rk[nr]→rk[0]）**。先用 FIPS 标准测试向量验证你的 AES 实现，再去调业务接口。

### 5. 接口逐个验证（真实请求，不许脑补）
- 分类 → 拿到 id/name
- 列表 → 确认分页参数（page/pageSize）、排序参数、返回 total
- 详情 → 确认字段映射
- 搜索 → 关键词实测有结果
- 播放 → 拿到真实 m3u8/mp4，curl 验证含 `#EXTM3U` 或为视频二进制；播放地址若有时效签名，必须运行时实时获取，禁止缓存硬编码

## 二、Spider 合约（严格遵守）

独立 `class Spider`，不继承基类。方法签名带默认值。文件内无 `print`、无 `__main__`。

```python
class Spider:
    def init(self, extend=""): ...          # 解析 extend（JSON 字符串或 dict）
    def destroy(self): ...
    def getDependence(self): return []
    def manualVideoCheck(self): return False
    def action(self, action): return {}
    def isVideoFormat(self, url): ...       # 是否直链视频

    def homeContent(self, filter=False):
        # {"class": [{"type_id","type_name"}], "list": [vod], "filters": {...}}

    def homeVideoContent(self):
        # {"list": [vod]}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        # {"list":[...], "page":pg, "pagecount":N, "limit":20, "total":N}
        # 404/空页返回空 list，不抛异常

    def detailContent(self, ids):
        # {"list": [vod详情]}

    def searchContent(self, key, quick=False, pg="1"):
        # {"list": [...]}

    def playerContent(self, flag, ids, vipFlags=None):
        # {"parse": 0, "url": 直链, "header": {...}}

    def localProxy(self, param):
        # [200, "mime", bytes, None]
```

vod 字段：
- 列表项：`vod_id`、`vod_name`、`vod_pic`、`vod_remarks`（时长/备注）
- 详情追加：`vod_content`、`vod_year`、`vod_area`、`vod_actor`、`vod_director`、`vod_tag`
- 播放：`vod_play_from` = `"线路1$$$线路2"`，`vod_play_url` = `"正片$<id或url>$$$正片$<id或url>"`，from 与 url 的 `$$$` 分段一一对应

playerContent：
- 直连：`{"parse": 0, "url": "<m3u8/mp4>", "header": {...}}`
- 需代理：`"url": "proxy://do=m3u8&url=" + quote(原地址)`，localProxy 按 `do` 分发处理

## 三、网络层

- header 为 dict，带正常 UA 和 Referer。
- 类内三别名：`self.s = self.session = self.sess = requests.Session()`；无 requests 时降级 urllib。
- 超时 10~15 秒；失败返回空结果，不抛异常。
- 签名接口遇到 401/403/419 → 刷新会话重试一次。

## 四、图片与 m3u8

- 封面先确认 curl 带 Referer 能否直开；不行则 `vod_pic` 走 TVBox 图片代理：
  `http://127.0.0.1:9978/proxy?do=py&type=img&url=<quote(原图)>`，localProxy 按 `type=img` 拉取返回（加密图先解密，按魔数返回正确 mime：JPEG/PNG/WEBP/GIF）。
- m3u8 含相对分片：先试**直连**（多数壳按标准 HLS 能解析相对路径）；不行再用 localProxy 全量重写为绝对路径。

## 五、交付前自测（逐项真实跑过）

1. homeContent：分类、列表非空，每条有 id/name/pic
2. categoryContent：pg=1/2 内容不同，pagecount 与 total 自洽，非法页返回空 list
3. detailContent：vod_play_from 与 vod_play_url 分段数一致
4. searchContent：常见关键词有结果
5. playerContent：返回 url 能拉到 `#EXTM3U` 或视频头
6. localProxy：图片代理返回 200 且为有效图片字节
7. `python3 -m py_compile` 通过

## 七、实战提炼（只收新技术，不堆案例）

- **接口枚举**：全量 `grep -hoE '"/api/[a-zA-Z/_-]+"'`，不预设关键词；一个接口 401 不等于整站需登录，先确认有无匿名接口族。
- **自写 AES**：解密轮密钥必须逆序（rk[nr]→rk[0]）；先用 FIPS 标准向量验证实现，再调业务接口（有 pycryptodome 的机器测不出纯 Python 兜底的 bug）。
- **Cloudflare 对抗**：优先复用 `cf_clearance`（实测不绑 IP/UA），别硬刚验证逻辑；分发版必须写清过期自助更换流程。
- **图片代理**：图片域被拦且壳不带 cookie 时，在 spider 内起本地 HTTP 服务（127.0.0.1 随机端口）源侧带 cookie 抓图再吐给壳，比 TVBox 自带 `proxy://` 通用。
- **播放签名时效**：`get_file` 类一次性 hash 不要在详情页缓存，`vod_play_url` 存 `详情页URL?q=清晰度`，`playerContent` 时现抓新鲜签名 → 302 → 直链。
- **实测迭代**：第一版能跑不等于真能用，必须走完"分类→列表→详情→搜索→播放→图片"全链路实测，修完再交付。
- **"按加密写"（spider 加壳）**：用户说"按加密写"时，用 `tools/pack_spider.py 源文件.py` 打包。格式：整个源码 base64 切 64 字符一行塞进 `_PAYLOAD` 元组，运行时 `b64decode(''.join(_PAYLOAD))`（注意原版暮色影视写法直接传元组会 TypeError，必须先 join），sha256 校验通过才 `exec(compile(...), globals())`；校验失败抛 `RuntimeError('payload integrity check failed')`。用调用方 globals() 透传 `__name__`，TVBox import 时自测块不跑，直接 python 运行则照跑。只是防抄藏域名（base64 可逆），别当真安全手段。
- **封面先查协议再动手**：封面全挂先看是不是 `http://` 明文——Android 9+ 默认拦截 http，App 里全黑。能 https 就 https 直链（先验：证书有效、无 Referer/UA 校验、200 正常），这是最简单的修法；localProxy 中转只在 443 被干扰时作兜底，别一上来就上代理（多一跳、依赖 9978 端口）。
- **localProxy 取参先 unquote**：TVBox 传过来的 `url` 参数可能是 percent-encoded；`https%3A...` 会被 `startswith("http")` 蒙混过关，随后请求畸形地址报 ValueError——必须先 `urllib.parse.unquote` 再用。
- **localProxy 失败只回 200+占位图**：任何失败路径（坏参、空数据、404、超时、解密失败）都返回 `[200, "image/gif", blank_pixel]`（1x1 透明 GIF，43 字节可内联），别回 4xx/5xx——App 图片加载器遇到错误码可能弹坏图图标或反复重试，200 占位则静默跳过，不阻塞海报墙。
- **解析 robustness**：lxml/etree 解析为主、正则为兜底（`try: from lxml import etree except: etree=None`），比纯正则抗改版；年份筛选动态生成（`range(当年, 2009, -1)`）不用每年改代码；水印关键词集中成常量（如 `SITE_TITLE`）统一过滤。
- **别轻易说"修不了"（有料封面事件教训）**：封面拉不到不一定是网络问题——先拿字节看魔数，不是 JPEG/PNG 头就怀疑内容被加密。有料的 `qgtp.m.*` 图床返回的是 XOR 加密图：经典解法是用已知文件头（JPEG `FF D8 FF E0`）与前 4 字节异或恢复密钥，再整体异或解密。更优解是找**明文源站**：同一路径换 S3 源站 host（`qgtp.m.*` → `qgjs.m.nzwkzj.com`）直接返回原图，连解密都省了——先试这个。localProxy 里对拉到的字节做魔数分流：raw JPEG/PNG 直接返回，base64 文本再走解密。手机端排查加本地日志（如 `yl_debug.log` 写到 `/sdcard/`），比盲猜快。
- **假滑块/假验证码直接伪造 cookie**：有些站点的滑块验证是纯前端演戏——JS"通过"后只是写几个 cookie（如随机串+时间戳），服务端只校验 cookie 存在与新鲜度。方法：读验证 JS，找到通过后设置的 cookie 名和生成规则，直接在请求头里伪造，不用真的拖滑块。先确认服务端校验逻辑：只查"有无+是否过期"就能伪造；若有签名/后端会话绑定，这招没用，别硬上。
- **间歇性 404 可能是限流**：有些站点不用 429，而是随机回 404 + 0 字节空响应。识别：同一 URL 重试后有时成功 → 不是真 404，是限流。处理：退避重试 + 请求间隔 + 响应体量/特征校验（真页面 > N KB；验证码页有固定特征串；空响应直接判失败重试）。真 404 是重试多少次都 404，别混淆。
- **翻页格式别猜，直接抄站内"下一页"**：分类翻页模板不要靠通用格式碰运气，先抓一页看"下一页/尾页"的真实 href（如本站是 `/vodtype/20-2.html` 而非 `---page/2.html`）。更坑的是**软 200 错乱页**：错模板可能返回 200 且有卡片，但标题分类名丢失（如"_第1页"）、内容不对版——校验必须看标题里的分类名+页码双重确认，标题里没有本分类名直接判失败，不能靠"有卡片就放行"兜底。
- **M3U8 切片去广告**（playerContent→localProxy→_clean_m3u8_text 三段式）：广告切片常伪装成正常 ts（甚至 .jpg 后缀），抓包提取三要素——M3U8 URL、完整响应体、广告特征（短时长如 0.08s、规律路径如 `^/\d{8}/[a-f0-9]{16}/seg_`、广告与正片之间有 `#EXT-X-DISCONTINUITY`、广告 Key 与正片 Key 不同域名）。状态机逐行清洗：删广告切片与其专属 Key，维护 `ad_pattern` 正则库（per-site，如 `/mov/AD/`、`adjump`、广告域名）。两条铁律：① `#EXT-X-DISCONTINUITY` 必须在正片 `#EXT-X-KEY` 之前输出，否则解码器黑屏崩溃；② 切片与 Key URI 必须补全为公网绝对路径，否则播放器向 127.0.0.1 要切片报 404。Master 嵌套（有 `#EXT-X-STREAM-INF` 无 `#EXTINF`）先向下穿透一级再清洗。代理 URL 拼接用 `sep = "&" if "?" in base_proxy else "?"`（getProxyUrl 自带 `?do=py`，双问号会 Bad HTTP Status）。纯标准库实现。

## 八、工作方式

- 先逆向验证、接口全通，再写文件。
- 每一步用真实请求验证，不编造返回。
- 遇站方风控（429/403/人机验证）如实报告，不硬刷、不绕过。
- 交付时说明：分类数、已测链路、已知限制（如需登录必须明说）。
- 修东西不到最后一招不说不行：传输层（连通性）→内容层（拿字节看魔数，怀疑加密）→找替代（明文源站/解密/代理），每条路都试过再下结论；实在修不了，把试过的路和卡在哪一步说清楚。

- **文件命名规则**：文件名 = 网站的标题/显示品牌名。有中文显示名的用中文（如 `久久网.py`、`章鱼Play.py`）；没有中文名的用 `<title>` 里的英文品牌名原样照抄（含大小写，如 `Noodlemagazine.py`）。不用拼音，不加 debug/版本号后缀。定稿版去掉调试日志和 `print`。
- **非中文站默认翻译**：网站内容非中文的，标题默认翻成中文再返回（列表+详情都要翻）。实现：MyMemory 免费接口 `https://api.mymemory.translated.net/get?q=<batch>&langpair=<lp>`，按字符分批（每批 <400 字符防 QUERY LENGTH 超限），西里尔字母走 `ru|zh-CN`、其余走 `en|zh-CN`；已有中文/纯 hash 标题跳过；内存缓存译文；接口报错（responseStatus 非 200 或译文含 QUERY LENGTH/INVALID）保留原文、不缓存错误。类变量 `TRANSLATE = True` 作总开关。免费接口质量不稳、每页慢几秒，交付时明说。

- **分类以站点的权威定义为准**：写爬虫先探官方 API（`/api/v1/categories.php` 这类端点）和站内导航栏的真实分类体系，不能拿首页随手抓到的链接（如合集 slug）或标签搜索页凑数当分类。两次翻车：章鱼 Play 把 85 个合集 slug 当了分类，漏了官方 API 里真正的 3 个分类（动画/真人/无命名）；久久网用 13 个标签搜索页冒充分类，漏了真正的 64 个数字 id 分类（`/c/<id>`）。拿不到权威定义时，明说哪些是推测的。
- **Cloudflare TLS 指纹伪装（urllib 配方）**：站点在 Cloudflare 后、requests 全 403 时，不是头的问题，是 TLS 指纹。纯标准库解法：`ssl.create_default_context()` + `set_ciphers(Chrome TLS1.3/ECDHE 套件串)` + **`set_alpn_protocols(["http/1.1"])`（绝不能声明 h2，否则 Cloudflare 用 h2 回包而 urllib 解析失败报 BadStatusLine）** + `urllib.request.Request(url, headers=完整Chrome头)`；gzip 响应（`\x1f\x8b` 魔数或 Content-Encoding）手动 `gzip.decompress`。验证标志：伪装后 Cloudflare 不再回 403 验证页、直接开始回话。做成 `_get` 的自动备用通道：requests 正常走，403/异常才切伪装通道（10 秒超时），别在 `init` 里做网络探测（会拖慢启动被壳超时）。
- **403 managed challenge 别重试**：Cloudflare "Just a moment..."（`cType: 'managed'`）是人机验证页，不是硬封也不是限流——手机浏览器能过是因为自动跑了验证 JS，Python 跑不了。特征：403 + 约 6KB HTML + `challenge-platform` 脚本。处理：requests 遇到 403 直接 break 走备用通道（如上），重试无意义；`cf_clearance` cookie 方案只在用户浏览器被 challenge 过、能拿到该 cookie 时才可用，否则此路不通。
- **OK影视 传参兼容**：`categoryContent` 的 `filter` 可能是布尔值（`filter=True`），真正筛选项在 `extend` 里（dict 或 JSON 字符串）——代码不能对 filter 直接 `.get()`，要从 extend 取，最外层 try/except 兜底返回空 list；`pg` 可能是字符串 `'1'`；`homeContent(self, filter)` 必须给 filter 默认值，否则换调法会崩。四种调用组合（filter True/False × extend dict/None）都要测。
- **OK影视 图片代理不走 localProxy**：`proxy://do=py&type=img&url=` 和 `http://127.0.0.1:9978/proxy?do=py&type=img&url=` 两种**硬编码**写法在 OK影视 均不生效。正确姿势是用运行时提供的 `self.getProxyUrl()` 拼接：`getProxyUrl() + "&url=" + quote(原图) + "&type=img"`（注意是 `&` 不是 `?`，因为 getProxyUrl() 返回的串自带 `?do=`）。硬编码端口/协议是错的，要问运行时要地址。
- **封面可能是 XOR 加密图（xx9 案例）**：图片 CDN 返回的根本不是图片，是 XOR 加密二进制——首字节是 key，其余字节 `^ key`。Glide 直接解码必挂。修法：`_pic()` 里把封面全走 localProxy，localProxy 内先按魔数验（`_img_mime` 验 PNG/JPEG/GIF/WEBP 头），是明文直接返回；不是则 `key=raw[0]`、`table=bytes(i^key for i in range(256))`、`raw[1:].translate(table)` 解密后再验魔数返回。抓图时带 `Referer: https://<站点>/` + UA。这跟有料那次是同一类问题——封面先看字节魔数，别轻易判"修不了"。
