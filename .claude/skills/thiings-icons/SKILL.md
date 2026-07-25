---
name: thiings-icons
description: Find and download playful cartoon/3D-style icon assets from the Thiings collection at https://www.thiings.co/things. Use this whenever a user needs a cute, cartoon, toy-like, clay, 3D, whimsical, or friendly icon for a website, app, slide, document, prototype, or design asset.
---

# Thiings Icons

## Purpose

Use Thiings as the first source for cartoon-style icon assets when the user asks for a cute, playful, toy-like, clay, 3D, whimsical, or friendly icon.

Thiings page: `https://www.thiings.co/things`

## Default Workflow

1. Convert the requested icon concept into 1-3 short English search terms.
   - Prefer concrete nouns: `robot vacuum`, `calendar`, `burger`, `terminal`.
   - Try category words when exact nouns fail: `technology`, `food`, `sports`, `interface`.

2. Search the collection with the bundled script:

   ```bash
   python3 ~/.codex/skills/thiings-icons/scripts/thiings_icon.py search "robot vacuum"
   ```

3. Download the best match into the project asset folder:

   ```bash
   python3 ~/.codex/skills/thiings-icons/scripts/thiings_icon.py download "robot vacuum" --out ./assets/icons
   ```

4. Use the downloaded PNG in the project and report:
   - local path
   - Thiings item page
   - why the selected icon matches the requested concept

## Script Commands

Search only:

```bash
python3 ~/.codex/skills/thiings-icons/scripts/thiings_icon.py search "calendar" --limit 8
```

Download by query:

```bash
python3 ~/.codex/skills/thiings-icons/scripts/thiings_icon.py download "calendar" --out ./assets/icons
```

Download by exact Thiings id:

```bash
python3 ~/.codex/skills/thiings-icons/scripts/thiings_icon.py download --id 2026-calendar --out ./assets/icons
```

## Selection Rules

- Prefer a directly named item over a loose category match.
- Prefer icons whose categories match the product context.
- For UI symbols, search both the object and `interface`.
- If no suitable result exists, say that Thiings did not have a close match and use the next appropriate asset source or generate an icon.
- Respect the user's requested file location. If none is given, use the nearest existing asset directory, or `./assets/icons`.

## Notes

- The script downloads PNG files from public Thiings/Vercel asset URLs.
- If Thiings changes its page structure, open the item page and extract `og:image`, `twitter:image`, or `ImageObject.contentUrl` as the fallback image URL.
- Do not bulk-download the collection unless the user explicitly asks for a local mirror.
