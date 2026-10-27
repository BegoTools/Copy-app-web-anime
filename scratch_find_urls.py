import re, sys
sys.stdout.reconfigure(encoding="utf-8")
for p in ["dist/PPSA91360/assets/web/app.js", "ps5_native_src/src/main.cpp"]:
    t = open(p, encoding="utf-8", errors="ignore").read()
    urls = sorted(set(re.findall(r"https?://[^\s'\"`)\\]+", t)))
    print("==", p, len(t))
    for u in urls[:40]:
        print(u)
    for m in re.finditer(r"(baseUrl|BASE_URL|API_BASE|apiBase|/api/[a-zA-Z_/]+)", t):
        pass
    print(sorted(set(re.findall(r"/api/[a-zA-Z0-9_/\-]+", t)))[:60])
