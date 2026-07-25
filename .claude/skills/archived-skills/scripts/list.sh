#!/bin/bash
ARCHIVE="$HOME/.skills-archive"
echo "=== Archived Skills ==="
echo "Location: $ARCHIVE"
echo ""
count=0
for d in "$ARCHIVE"/*/; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  [ -f "$d/SKILL.md" ] || continue
  desc=$(grep -m1 '^description:' "$d/SKILL.md" 2>/dev/null | cut -d: -f2- | sed 's/^[ "]*//;s/[ "]*$//' | head -c 160)
  printf "• %-35s %s\n" "$name" "$desc"
  count=$((count+1))
done
echo ""
echo "Total archived: $count"
echo "To get details: archived-skills info <name>"
echo "To restore:     archived-skills restore <name>"
