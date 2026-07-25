# Rich Text Batch Notes

Use this when:
- the user wants Apple Notes as the final reading surface
- the content is long-form and structured
- interactive `memo` flows are inconvenient
- plain/preformatted imports would degrade the reading experience

Default bias:
- if the user wants detailed reading material and does not ask for concision, make the first notes full-length
- do not intentionally start with abbreviated note bodies and plan to expand only after feedback
- if the request is a book breakdown and no target is specified, assume Apple Notes is the target when this skill is in play

## 1. Prefer app-native rich text for direct-reading deliverables

If the user wants notes that read well inside Apple Notes:
- prefer creating notes with a rich HTML body
- avoid wrapping the whole note in preformatted/plain text unless raw text preservation is the goal

## 2. Batch creation discipline

For many notes:
- create them in batches
- use exact folder names and note titles
- make the first batch representative of the final target density
- after each batch, verify:
  - folder exists
  - expected note count
  - one sample note body reads back correctly

Folder structure:
- one book -> one folder
- multiple books / article series -> one parent folder plus one child folder per book or cluster when supported
- parent folder should keep overall notes such as:
  - 导读
  - 总体地图
  - 对比阅读
  - 使用说明

## 3. Verification loop

Minimum verification after a batch:
- list note titles in the target folder
- count notes
- read one representative note body

If later batches are much shorter than earlier ones:
- treat it as a content-quality regression, not merely a formatting issue

## 4. When `memo` is not enough

`memo` is good for routine Notes management.

For rich-text bulk delivery:
- use Apple Notes automation that can set the note body directly
- preserve headings, lists, and emphasis in the created note

## 5. Common pitfalls

- assuming Markdown import will automatically become readable rich text
- bulk-creating notes without counting them
- checking only the first note and not the later notes
- treating successful creation as proof of acceptable reading quality
