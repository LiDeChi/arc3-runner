#!/bin/bash
name="$1"
ARCHIVE="$HOME/.skills-archive"
CENTRAL="$HOME/.skills"
if [ -z "$name" ]; then
  echo "Usage: archived-skills restore <skill-name>"
  exit 1
fi
src="$ARCHIVE/$name"
dst="$CENTRAL/$name"
if [ ! -d "$src" ]; then
  echo "ERROR: '$name' not found in archive at $src"
  exit 1
fi
if [ -e "$dst" ]; then
  echo "WARNING: $dst already exists. Aborting to avoid overwrite."
  echo "Remove it first if you really want to restore from archive."
  exit 1
fi
cp -a "$src" "$dst"
echo "✓ Restored '$name' → $dst"
echo ""
echo "Next step (recommended):"
echo "  ~/.skills/sync-skills/scripts/sync.sh sync-all"
echo ""
echo "This will make the skill available across Grok, Claude, Gemini, Codex etc."
