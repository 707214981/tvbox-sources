#!/usr/bin/env python3
"""一次性导入第三方 spider（供 GitHub Actions 调用）
- 读取 tools/spider_import.json，从原始 URL 下载 py/js 到 spiders/
- 按内容哈希跳过与已存在文件重复的
- 更新 spiders/index.json（文件名 -> 展示名）
- 之后由 gen_tvbox_json.py 重新生成 tvbox.json 并提交
用法: python3 tools/import_spiders.py
"""
import json, os, re, hashlib, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPIDERS = os.path.join(BASE, "spiders")
UA = {"User-Agent": "Mozilla/5.0"}

def norm_api(api):
    m = re.match(r'https?://[^/]+/(https?://.+|github\.com/.+)', api)
    if m:
        u = m.group(1)
        u = u if u.startswith('http') else 'https://' + u
    else:
        u = api
    return urllib.parse.quote(u, safe=':/?#[]@!$&\'()*+,;=%')

def get(url, timeout=30):
    req = urllib.request.Request(norm_api(url), headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read()

def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()[:12]

def main():
    os.makedirs(SPIDERS, exist_ok=True)
    manifest = json.load(open(os.path.join(BASE, "tools", "spider_import.json"), encoding="utf-8"))
    index_path = os.path.join(SPIDERS, "index.json")
    index = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else {}
    existing_hashes = set()
    for dp, _, fns in os.walk(SPIDERS):
        for fn in fns:
            if fn.endswith((".py", ".js")):
                existing_hashes.add(file_hash(os.path.join(dp, fn)))

    added, skipped, failed = 0, 0, []
    for m in manifest:
        fn, api = m["file"], m["api"]
        dest = os.path.join(SPIDERS, fn)
        if os.path.exists(dest):
            skipped += 1
            index.setdefault(fn, m["name"])
            continue
        try:
            data = get(api)
        except Exception as e:
            failed.append((fn, f"下载失败 {str(e)[:40]}"))
            continue
        if fn.endswith(".py"):
            try:
                txt = data.decode("utf-8", "replace")
                compile(txt, "<sp>", "exec")
                assert "homeContent" in txt
            except Exception as e:
                failed.append((fn, f"校验失败 {str(e)[:40]}"))
                continue
        if hashlib.sha256(data).hexdigest()[:12] in existing_hashes:
            skipped += 1
            continue
        with open(dest, "wb") as f:
            f.write(data)
        existing_hashes.add(hashlib.sha256(data).hexdigest()[:12])
        index[fn] = m["name"]
        added += 1
        print(f"  + {fn}", flush=True)

    json.dump(index, open(index_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"新增 {added}，跳过 {skipped}，失败 {len(failed)}")
    for fn, why in failed[:10]:
        print(f"  x {fn}: {why}")

if __name__ == "__main__":
    main()
