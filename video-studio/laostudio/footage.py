"""ຫາ footage ອັດຕະໂນມັດ (ຮູບ ແລະ ວີດີໂອ) ພ້ອມບັນທຶກລິຂະສິດ.

Order for every `img:` / `video:` / `clip:` request
  1. the project's own  assets/  folder          (exact file name or keywords in the file name)
  2. the shared library folders                   (LAOSTUDIO_LIBRARY=dir1:dir2 or brand "library")
  3. Wikimedia Commons                            (free licences; author + licence saved to credits)
  4. Pexels (photos / stock video)                (only when PEXELS_API_KEY is set)
  5. a generated placeholder card                 (reported as missing so a human can fix it)
"""
import hashlib, html, json, os, re, subprocess, tempfile, time, urllib.parse

from .voice import CACHE

UA = "LaoVideoStudio/1.0 (football explainer videos; contact via repository)"
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
VID_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v")
SKIP_WORDS = ("logo", "icon", "map", "flag", "kit ", "kit_", "diagram", "chart", "signature", "crest", "badge",
              "locator", "coat of arms", "emblem", "pictogram", "stub", ".svg")


def _norm(s):
    return re.sub(r"[^a-z0-9຀-໿]+", " ", s.lower()).strip()


class RateLimited(Exception):
    pass


_last = {}
_blocked = {}                                                 # host -> time when we may try again


def _curl(url, dest=None, headers=None, min_gap=2.0, tries=3):
    """Polite HTTP GET: one request per `min_gap` seconds per host, obeys Retry-After on 429.
    Wikimedia bans impatient clients for 10 minutes, so never loop over candidates after a 429."""
    host = urllib.parse.urlparse(url).netloc
    for attempt in range(tries):
        if _blocked.get(host, 0) > time.time():
            raise RateLimited(f"{host} ຂໍໃຫ້ລໍຖ້າອີກ {int(_blocked[host] - time.time())} ວິນາທີ")
        wait = _last.get(host, 0) + min_gap - time.time()
        if wait > 0:
            time.sleep(wait)
        hdr = tempfile.mktemp(suffix=".hdr")
        out = dest + ".part" if dest else tempfile.mktemp(suffix=".body")
        cmd = ["curl", "-sS", "-L", "-m", "120", "-A", UA, "-D", hdr, "-o", out, "-w", "%{http_code}"]
        for k, v in (headers or {}).items():
            cmd += ["-H", f"{k}: {v}"]
        r = subprocess.run(cmd + [url], capture_output=True, text=True)
        _last[host] = time.time()
        code = r.stdout.strip()[-3:]
        head = open(hdr, encoding="latin-1").read().lower() if os.path.exists(hdr) else ""
        if os.path.exists(hdr):
            os.remove(hdr)
        if code == "200":
            if dest:
                os.replace(out, dest)
                return dest
            body = open(out, encoding="utf-8", errors="replace").read(); os.remove(out)
            return body
        if os.path.exists(out):
            os.remove(out)
        if code == "429":
            m = re.search(r"retry-after:\s*(\d+)", head)
            ra = int(m.group(1)) if m else 60
            if ra > 45 or attempt == tries - 1:
                _blocked[host] = time.time() + ra
                raise RateLimited(f"{host} ຈຳກັດຄວາມໄວ (429) — ລອງໃໝ່ໃນ {ra} ວິນາທີ")
            time.sleep(ra + 1)
            continue
        raise RuntimeError(f"HTTP {code or r.stderr.strip()[-120:]}")
    raise RuntimeError("retry exhausted")


def _get_json(url, headers=None):
    """JSON GET with a 7-day disk cache (re-runs make no network requests)."""
    f = os.path.join(CACHE, "search", hashlib.sha1(url.encode()).hexdigest()[:20] + ".json")
    if os.path.exists(f) and time.time() - os.path.getmtime(f) < 7 * 86400:
        return json.load(open(f, encoding="utf-8"))
    data = json.loads(_curl(url, headers=headers))
    os.makedirs(os.path.dirname(f), exist_ok=True)
    json.dump(data, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    return data


class Finder:
    def __init__(self, project_dir, cfg, online=True):
        self.project = project_dir
        self.online = online
        self.dirs = [os.path.join(project_dir, "assets")]
        lib = os.environ.get("LAOSTUDIO_LIBRARY", "")
        self.dirs += [d for d in lib.split(os.pathsep) if d] + list(cfg.get("library", []) or [])
        self.used, self.credits, self.missing, self._search = set(), [], [], {}
        self.index = []
        for d in self.dirs:
            for root, _, files in os.walk(d) if os.path.isdir(d) else []:
                for f in files:
                    if f.lower().endswith(IMG_EXT + VID_EXT):
                        self.index.append((os.path.join(root, f), _norm(os.path.splitext(f)[0])))

    # ---------------------------------------------------------------- local
    def _local(self, q, kind, n):
        for d in self.dirs:                                   # exact relative path / file name
            p = os.path.join(d, q)
            if os.path.isfile(p):
                return p
        words = _norm(q).split()
        hits = [p for p, name in self.index if words and all(w in name for w in words)
                and (p.lower().endswith(VID_EXT) if kind in ("clip", "video") else True)]
        if kind == "clip" and not hits:
            return None
        hits.sort()
        fresh = [p for p in hits if p not in self.used]
        pool = fresh or hits
        return pool[(n - 1) % len(pool)] if pool else None

    # ---------------------------------------------------------------- Wikimedia Commons
    def _commons(self, q, kind):
        key = ("commons", q, kind)
        if key in self._search:
            return self._search[key]
        ft = "filetype:video" if kind == "video" else "filetype:bitmap"
        url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} {ft}",
            "gsrnamespace": 6, "gsrlimit": 30, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1920,
            "iiextmetadatafilter": "LicenseShortName|Artist|Credit"})
        res = []
        try:
            pages = _get_json(url).get("query", {}).get("pages", {})
        except Exception as e:
            print(f"  ! Commons ຄົ້ນບໍ່ໄດ້ ({q}): {e}")
            pages = {}
        for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
            ii = (p.get("imageinfo") or [{}])[0]
            title, mime = p.get("title", ""), ii.get("mime", "")
            w, h, size = ii.get("width", 0), ii.get("height", 0), ii.get("size", 0)
            low = title.lower()
            if any(s in low for s in SKIP_WORDS) and not any(s.strip() in q.lower() for s in SKIP_WORDS):
                continue
            if kind == "video":
                if not mime.startswith("video/") or size > 80e6:
                    continue
            elif mime not in ("image/jpeg", "image/png") or min(w, h) < 500 or w < 800 or size > 30e6:
                continue
            em = ii.get("extmetadata", {})
            artist = re.sub(r"<[^>]+>", "", html.unescape(em.get("Artist", {}).get("value", ""))).strip()
            url_ = ii.get("url")
            thumb = ii.get("thumburl", "")
            if kind != "video" and size > 4e6 and urllib.parse.urlparse(thumb).netloc == "upload.wikimedia.org":
                url_ = thumb
            res.append({"url": url_, "title": title.replace("File:", ""), "w": w, "h": h,
                        "license": em.get("LicenseShortName", {}).get("value", "?"),
                        "author": re.sub(r"\s+", " ", artist)[:80] or "?", "page": ii.get("descriptionurl", ""),
                        "source": "Wikimedia Commons"})
        self._search[key] = res
        return res

    # ---------------------------------------------------------------- Pexels
    def _pexels(self, q, kind):
        api = os.environ.get("PEXELS_API_KEY")
        key = ("pexels", q, kind)
        if not api:
            return []
        if key in self._search:
            return self._search[key]
        res = []
        try:
            if kind == "video":
                d = _get_json("https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
                    {"query": q, "per_page": 15}), {"Authorization": api})
                for v in d.get("videos", []):
                    files = sorted((f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"
                                    and (f.get("width") or 0) <= 1920), key=lambda f: -(f.get("width") or 0))
                    if files:
                        res.append({"url": files[0]["link"], "title": f"pexels-{v['id']}.mp4", "w": files[0]["width"],
                                    "h": files[0]["height"], "license": "Pexels License",
                                    "author": v.get("user", {}).get("name", "?"), "page": v.get("url", ""),
                                    "source": "Pexels"})
            else:
                d = _get_json("https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
                    {"query": q, "per_page": 20}), {"Authorization": api})
                for p in d.get("photos", []):
                    res.append({"url": p["src"]["large2x"], "title": f"pexels-{p['id']}.jpg", "w": p["width"],
                                "h": p["height"], "license": "Pexels License", "author": p.get("photographer", "?"),
                                "page": p.get("url", ""), "source": "Pexels"})
        except Exception as e:
            print(f"  ! Pexels ຄົ້ນບໍ່ໄດ້ ({q}): {e}")
        self._search[key] = res
        return res

    def _download(self, item):
        ext = os.path.splitext(urllib.parse.urlparse(item["url"]).path)[1].lower() or ".jpg"
        dest = os.path.join(CACHE, "footage", hashlib.sha1(item["url"].encode()).hexdigest()[:20] + ext)
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            _curl(item["url"], dest, min_gap=3.0)
        return dest

    # ---------------------------------------------------------------- public
    def find(self, media):
        """media = {'kind': img|video|clip, 'q': query, 'n': nth result}. Returns local path or None."""
        q, kind, n = media["q"], media["kind"], media.get("n", 1)
        p = self._local(q, kind, n)
        if p:
            self.used.add(p)
            return p
        if kind == "clip" or not self.online:
            self.missing.append(q)
            return None
        results = self._commons(q, kind) + self._pexels(q, kind)
        if kind == "video" and not results:                    # no stock video -> fall back to a photo
            kind = "img"; results = self._commons(q, kind) + self._pexels(q, kind)
        if not results and len(q.split()) > 2:                 # too specific: drop the last word and retry
            results = self._commons(" ".join(q.split()[:-1]), kind)
        fresh = [r for r in results if r["url"] not in self.used]
        pool = fresh if (media.get("auto") or n == 1) else results
        pool = pool or results
        fails = 0
        for item in pool[(n - 1) % len(pool):] + pool[:(n - 1) % len(pool)] if pool else []:
            try:
                path = self._download(item)
            except RateLimited as e:
                print(f"  ! {e}")
                break
            except Exception as e:
                print(f"  ! ດາວໂຫຼດບໍ່ໄດ້ {item['title'][:50]}: {e}")
                fails += 1
                if fails >= 2:
                    break
                continue
            self.used.add(item["url"])
            if not any(c["title"] == item["title"] for c in self.credits):
                self.credits.append({k: item[k] for k in ("title", "author", "license", "page", "source")})
            return path
        self.missing.append(q)
        return None
