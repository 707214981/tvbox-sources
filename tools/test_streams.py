#!/usr/bin/env python3
"""
直播流可用性抽查
- 读取 staging/stream_samples.json，对每个源抽查最多 8 条流
- 用 curl 探测（HEAD → Range GET 首字节），8s 超时
- 先测金丝雀 URL，若金丝雀不通则判定为代理凭证轮换，停止测试、保留旧结果
- 结果写回 staging/manifest.json 的 stream_test 字段
用法: python3 test_streams.py [--staging DIR]
"""
import json, os, sys, subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

STAGING = sys.argv[sys.argv.index("--staging") + 1] if "--staging" in sys.argv else os.path.join(os.path.dirname(os.path.abspath(__file__)), "staging")
CANARY = "https://api.github.com/zen"
TIMEOUT = 8
WORKERS = 8

def curl_ok(url):
    # HEAD 探测
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "-I", "--max-time", str(TIMEOUT), url],
                       capture_output=True, text=True, timeout=TIMEOUT + 5)
    code = r.stdout.strip()
    if code.startswith("2") or code.startswith("3"):
        return True
    # 部分流不支持 HEAD，改用 Range 取首字节
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}:%{size_download}",
                        "--max-time", str(TIMEOUT), "-r", "0-1023", url],
                       capture_output=True, text=True, timeout=TIMEOUT + 5)
    try:
        code, size = r.stdout.strip().split(":")
        return (code.startswith("2") or code == "206") and int(size) > 0
    except Exception:
        return False

def main():
    samples_path = os.path.join(STAGING, "stream_samples.json")
    manifest_path = os.path.join(STAGING, "manifest.json")
    if not os.path.exists(samples_path):
        print("no stream_samples.json, skip")
        return
    samples = json.load(open(samples_path))
    manifest = json.load(open(manifest_path))
    by_file = {m["file"]: m for m in manifest}

    print("canary check...", flush=True)
    if not curl_ok(CANARY):
        print("CANARY FAILED: network/proxy issue, keep old results", flush=True)
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tested_files = 0
    for fname, urls in samples.items():
        if not urls or fname not in by_file:
            continue
        # 每批之前都先过金丝雀（防凭证中途轮换）
        if not curl_ok(CANARY):
            print("canary failed mid-run, stop", flush=True)
            break
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            results = list(ex.map(curl_ok, urls))
        ok = sum(1 for r in results if r)
        by_file[fname]["stream_test"] = {"tested": len(urls), "ok": ok, "at": now}
        tested_files += 1
        print(f"  {fname}: {ok}/{len(urls)}", flush=True)

    json.dump(manifest, open(manifest_path, "w"), ensure_ascii=False, indent=1)
    print(f"Done: tested {tested_files} files")

if __name__ == "__main__":
    main()
