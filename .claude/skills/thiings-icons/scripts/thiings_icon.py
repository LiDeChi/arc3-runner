#!/usr/bin/env python3
import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://www.thiings.co"
THINGS_URL = f"{BASE_URL}/things"
BLOB_BASE = "https://lftz25oez4aqbxpq.public.blob.vercel-storage.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X) thiings-icons-skill/1.0"


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", errors="replace")


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as res:
        return res.read(), res.headers.get("content-type", "")


def unescape_next_text(text):
    text = html.unescape(text)
    text = text.replace("\\u0026", "&")
    text = text.replace('\\"', '"')
    return text


def parse_items(page_text):
    text = unescape_next_text(page_text)
    pattern = re.compile(
        r'\{"id":"(?P<id>[^"]*)","name":"(?P<name>[^"]*)","categories":\[(?P<categories>[^\]]*)\],"fileId":"(?P<file_id>[^"]+)","shareUrl":"(?P<share_url>[^"]+)"',
        re.S,
    )
    items = []
    seen = set()
    for match in pattern.finditer(text):
        item_id = match.group("id")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        categories = re.findall(r'"([^"]+)"', match.group("categories"))
        items.append(
            {
                "id": item_id,
                "name": match.group("name"),
                "categories": categories,
                "file_id": match.group("file_id"),
                "share_url": match.group("share_url"),
            }
        )
    return items


def load_items():
    return parse_items(fetch_text(THINGS_URL))


def words(value):
    return re.findall(r"[a-z0-9]+", value.lower())


def score_item(query, item):
    q_words = words(query)
    name = item["name"].lower()
    item_id = item["id"].lower()
    cats = " ".join(item["categories"]).lower()
    haystack = f"{name} {item_id} {cats}"

    score = 0
    query_l = query.lower().strip()
    if query_l == name or query_l == item_id.replace("-", " "):
        score += 100
    if query_l in name or query_l in item_id.replace("-", " "):
        score += 55
    if query_l in cats:
        score += 25
    for word in q_words:
        if word in words(name):
            score += 14
        elif word in words(item_id):
            score += 10
        elif word in words(cats):
            score += 6
        elif word in haystack:
            score += 2
    return score


def search_items(items, query, limit):
    ranked = sorted(
        ((score_item(query, item), item) for item in items),
        key=lambda pair: (-pair[0], pair[1]["name"].lower()),
    )
    return [(score, item) for score, item in ranked if score > 0][:limit]


def image_url_from_file_id(file_id):
    return f"{BLOB_BASE}/image-{file_id}.png"


def image_url_from_detail_page(share_url):
    text = fetch_text(share_url)
    candidates = []
    for pattern in (
        r'<meta property="og:image" content="([^"]+)"',
        r'<meta name="twitter:image" content="([^"]+)"',
        r'"contentUrl":"([^"]+)"',
        r'"imageUrl":"([^"]+)"',
    ):
        candidates.extend(re.findall(pattern, text))
    for candidate in candidates:
        candidate = unescape_next_text(candidate)
        if candidate.startswith("https://"):
            return candidate
    raise RuntimeError(f"No image URL found on {share_url}")


def slugify(value):
    slug = "-".join(words(value))
    return slug or "thiings-icon"


def choose_item(args, items):
    if args.id:
        for item in items:
            if item["id"] == args.id:
                return item
        raise SystemExit(f"No Thiings item found with id: {args.id}")
    matches = search_items(items, args.query, 1)
    if not matches:
        raise SystemExit(f"No Thiings matches found for query: {args.query}")
    return matches[0][1]


def command_search(args):
    items = load_items()
    matches = search_items(items, args.query, args.limit)
    if not matches:
        print(f"No matches for: {args.query}")
        return 1
    for score, item in matches:
        print(
            json.dumps(
                {
                    "score": score,
                    "id": item["id"],
                    "name": item["name"],
                    "categories": item["categories"],
                    "share_url": item["share_url"],
                    "image_url": image_url_from_file_id(item["file_id"]),
                },
                ensure_ascii=False,
            )
        )
    return 0


def command_download(args):
    items = load_items()
    item = choose_item(args, items)
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slugify(item['name'])}.png"

    candidates = [image_url_from_file_id(item["file_id"])]
    try:
        detail_url = image_url_from_detail_page(item["share_url"])
        if detail_url not in candidates:
            candidates.append(detail_url)
    except Exception:
        pass

    errors = []
    for url in candidates:
        try:
            data, content_type = fetch_bytes(url)
            if not data.startswith(b"\x89PNG") and "image" not in content_type:
                raise RuntimeError(f"unexpected content type: {content_type}")
            out_path.write_bytes(data)
            print(
                json.dumps(
                    {
                        "path": str(out_path),
                        "id": item["id"],
                        "name": item["name"],
                        "categories": item["categories"],
                        "share_url": item["share_url"],
                        "image_url": url,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        except (urllib.error.URLError, RuntimeError) as exc:
            errors.append(f"{url}: {exc}")

    raise SystemExit("Download failed:\n" + "\n".join(errors))


def main():
    parser = argparse.ArgumentParser(description="Search and download Thiings icons.")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search Thiings icons")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.set_defaults(func=command_search)

    download = sub.add_parser("download", help="Download the best Thiings icon match")
    download.add_argument("query", nargs="?", default="")
    download.add_argument("--id", help="Exact Thiings item id")
    download.add_argument("--out", default="./assets/icons")
    download.set_defaults(func=command_download)

    args = parser.parse_args()
    if args.command == "download" and not args.id and not args.query:
        parser.error("download requires a query or --id")
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
