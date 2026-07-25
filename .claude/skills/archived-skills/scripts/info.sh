#!/bin/bash
name="$1"
ARCHIVE="$HOME/.skills-archive"
if [ -z "$name" ]; then
  echo "Usage: archived-skills info <skill-name>"
  exit 1
fi
path="$ARCHIVE/$name"
if [ ! -d "$path" ]; then
  echo "Skill '$name' not found in archive."
  exit 1
fi
echo "=== $name ==="
echo "Path: $path"
echo ""
if [ -f "$path/SKILL.md" ]; then
  echo "--- Full frontmatter + description ---"
  head -30 "$path/SKILL.md"
  echo ""
  echo "Full SKILL.md location: $path/SKILL.md"
  echo "You can Read this file directly with the Read tool."
fi
