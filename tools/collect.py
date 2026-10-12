#!/usr/bin/env python3
"""TVBox 源每日采集（GitHub Actions 版）
- git clone 上游仓库（shallow），按 SOURCES 清单拷贝文件到 staging/
- 与本地 collect.py 同 manifest 格式；写文件不做切分（Actions 内 git 无单参数限制）
- 首次运行会清理旧的 *.part* 切分文件
用法: python3 tools/collect.py [--staging staging]
"""
import json, os, re, sys, subprocess, hashlib, shutil
from datetime import datetime, timezone

SOURCES = [
    ("adminouyang", "231006", ["py"], "vod_py"),
    ("adminouyang", "231006", ["tvbox/点播源"], "vod_txt"),
    ("adminouyang", "231006", ["tvbox/直播源"], "live_txt"),
    ("adminouyang", "231006", ["py/TV/output/ipv4", "py/TV/output/ipv6"], "live_txt"),
    ("royalhayga", "tvbox-master-aggregator", ["tvbox.json"], "vod_json"),
    ("hujingguang", "ChinaIPTV", [""], "live_m3u"),
    ("dongyubin", "IPTV", [""], "live_m3u"),
    ("yy-niuma", "live-tv", [""], "live_m3u"),
]

EXTS = {
    "vod_py":   {".py"},
    "vod_json": {".json"},
    "vod_txt":  {".txt"},
    "live_m3u": {".m3u", ".m3u8"},
    "live_txt": {".txt"},
}
CATDIR = {"vod_py": "vod/py", "vod_json": "vod/json", "vod_txt": "vod/txt",
          "live_m3u": "live/m3u", "live_txt": "live/txt"}
MAX_FILE_SIZE = 2 * 1024 * 1024
STAGING = sys.argv[sys.argv.index("--staging") + 1] if "--staging" in sys.argv else os.path.join(os.environ.get("TVBOX_ROOT", os.getcwd()), "staging")
WORK = "/tmp/upstream"

def parse_streams_m3u(text):
    return [l.strip() for l in text.splitlines()
            if l.strip() and not l.strip().startswith("#") and re.match(r"^https?://", l.strip())]

def parse_streams_txt(text):
    urls = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.rsplit(",", 1)
        if len(parts) == 2 and re.match(r"^https?://", parts[1].strip()):
            urls.append(parts[1].strip())
        elif re.match(r"^https?://", line):
            urls.append(line)
    return urls

def validate(text, category):
    if category == "vod_py":
        try:
            compile(text, "<py>", "exec")
            return True, "syntax ok"
        except SyntaxError as e:
            return False, f"syntax error: {e}"
    if category == "vod_json":
        try:
            json.loads(text)
            return True, "json ok"
        except Exception as e:
            return False, f"json error: {e}"
    if category == "live_m3u":
        if not text.lstrip().startswith("#EXTM3U"):
            return False, "missing #EXTM3U"
        n = len(parse_streams_m3u(text))
        return (True, f"{n} streams") if n else (False, "no streams")
    if category in ("live_txt", "vod_txt"):
        n = len(parse_streams_txt(text))
        return True, f"{n} url lines"
    return True, "ok"

def safe_name(owner, repo, path):
    base = re.sub(r'[^\w\u4e00-\u9fff.\- ]', '_', path.replace("/", "_")).strip()
    return f"{owner}-{repo}__{base}"

_cloned = {}
def clone(owner, repo):
    key = f"{owner}/{repo}"
    if key not in _cloned:
        dest = os.path.join(WORK, f"{owner}_{repo}")
        if os.path.exists(dest):
            shutil.rmtree(dest)
        print(f"clone {key} ...", flush=True)
        subprocess.run(["git", "clone", "--depth", "1", f"https://github.com/{key}.git", dest],
                       check=True, capture_output=True, timeout=300)
        _cloned[key] = dest
    return _cloned[key]

def walk_local(root, exts, depth=0):
    out = []
    if depth > 4:
        return out
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return out
    for name in entries:
        p = os.path.join(root, name)
        if os.path.isdir(p):
            out += walk_local(p, exts, depth + 1)
        elif os.path.isfile(p):
            _, dot, ext = name.lower().rpartition(".")
            if dot and ("." + ext) in exts and 0 < os.path.getsize(p) <= MAX_FILE_SIZE:
                out.append(p)
    return out

def main():
    os.makedirs(STAGING, exist_ok=True)
    # 清理旧的切分文件（历史原因，Actions 内不需要切分）
    for dp, _, fns in os.walk(STAGING):
        for fn in fns:
            if re.search(r"\.part\d+\.", fn):
                os.remove(os.path.join(dp, fn))
                print(f"  del stale {fn}")
    manifest_path = os.path.join(STAGING, "manifest.json")
    old = {}
    if os.path.exists(manifest_path):
        old = {m["file"]: m for m in json.load(open(manifest_path, encoding="utf-8"))}
    manifest, now = [], datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for owner, repo, paths, category in SOURCES:
        subdir = os.path.join(STAGING, CATDIR[category])
        os.makedirs(subdir, exist_ok=True)
        print(f"== {owner}/{repo} [{category}] ==", flush=True)
        try:
            root = clone(owner, repo)
        except Exception as e:
            print(f"  ! clone failed: {e}", flush=True)
            continue
        for path in paths:
            full = os.path.join(root, path) if path else root
            files = []
            if os.path.isfile(full):
                files = [full]
            elif os.path.isdir(full):
                files = walk_local(full, EXTS[category])
            else:
                print(f"  ! no such path: {path}", flush=True)
                continue
            for f in files:
                rel_in_repo = os.path.relpath(f, root)
                fname = safe_name(owner, repo, rel_in_repo)
                dest = os.path.join(subdir, fname)
                try:
                    with open(f, encoding="utf-8", errors="replace") as fh:
                        text = fh.read()
                except Exception as e:
                    print(f"  x {fname}: read failed {e}", flush=True)
                    continue
                ok, note = validate(text, category)
                if not ok:
                    print(f"  x {fname}: invalid ({note})", flush=True)
                    continue
                digest = hashlib.sha256(text.encode()).hexdigest()[:12]
                rel = os.path.relpath(dest, STAGING)
                prev = old.get(rel)
                stream_urls = []
                if category in ("live_m3u", "live_txt"):
                    stream_urls = (parse_streams_m3u(text) if category == "live_m3u"
                                   else parse_streams_txt(text))[:8]
                if prev and prev.get("sha") == digest and os.path.exists(dest):
                    prev["stream_sample"] = stream_urls
                    manifest.append(prev)
                    continue
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(text)
                manifest.append({
                    "file": rel, "source": f"{owner}/{repo}", "source_path": rel_in_repo,
                    "category": category, "size": len(text), "sha": digest,
                    "validate": note, "stream_test": prev.get("stream_test") if prev else None,
                    "stream_sample": stream_urls, "updated": now,
                })
                print(f"  + {fname} ({len(text)}B, {note})", flush=True)

    manifest = [m for m in manifest if os.path.exists(os.path.join(STAGING, m["file"]))]
    manifest.sort(key=lambda m: m["file"])
    samples = {m["file"]: m.pop("stream_sample", []) for m in manifest}
    json.dump(manifest, open(manifest_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(samples, open(os.path.join(STAGING, "stream_samples.json"), "w", encoding="utf-8"))
    print(f"\nDone: {len(manifest)} files -> {manifest_path}")

if __name__ == "__main__":
    main()
