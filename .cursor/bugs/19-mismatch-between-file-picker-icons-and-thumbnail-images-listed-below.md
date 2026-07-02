---
github_issue: 90
---
# Mismatch between file picker icons and thumbnail images listed below

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Right now there's a mismatch between the file picker icons and the thumbnail icons listed below. For example, you can have two file picker icons display, but only one thumbnail, and when you clear a file picker icon, it doesn't clear the thumbnail. For a valid MVP, this must be fixed. 

I tried fixing this before, but it kept introducing even worse bugs, so this has to be fixed carefully.

## Acceptance criteria

- The thumbnail grid always matches the uploader's file chips one-to-one (same
  files, same names).
- Removing a file via the X on its chip removes its thumbnail on the next
  render.
- Uploading the same content twice shows both chips and both thumbnails (one
  marked "duplicate"); the duplicate is only processed once.
- "Clear all" empties both the chips and the thumbnails.
- No CSS hiding of the native file chips and no `st.rerun()` after upload (the
  two approaches that caused regressions in past attempts: an empty dropzone
  and a 5-10s mobile delay).
