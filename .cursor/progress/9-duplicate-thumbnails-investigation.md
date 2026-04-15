# Duplicate Thumbnails Investigation - Handoff

## Status
Issue #54 is ~~open~~ closed. The app is reverted to its original behavior (v0.9.6): native file chips with the small cross show alongside the custom thumbnail grid. Functionally fine, cosmetically imperfect.

I decided to close the GitHub issue because it was too frustrating to work with this, and I decided to move on. I might revisit this later, but under a different GitHub issue. The current handoff document should not map to that existing GitHub issue that was closed. 

## Root Cause
Streamlit's `st.file_uploader` renders uploaded file items (chips) **inside** the dropzone element, not as siblings. The existing CSS selectors target `data-testid` values (`stFileUploaderFile`, `stFileUploaderFileName`, etc.) that no longer exist in current Streamlit versions. The actual values are now `stFileChips`, `stFileChip`, `stFileChipName`, `stFileChipDeleteBtn`.

## DOM Structure (Streamlit 1.53+)
```
<div data-testid="stFileUploader">
  <label>...</label>
  <section data-testid="stFileUploaderDropzone">
    <!-- EITHER chips (when files uploaded): -->
    <div>  <!-- StyledUploadedFiles -->
      <div data-testid="stFileChips">
        <div>  <!-- StyledFileChipList -->
          <div>  <!-- StyledFileChipListItem -->
            <div data-testid="stFileChip">
              <span data-testid="stFileChipName">filename</span>
              <button data-testid="stFileChipDeleteBtn">X</button>
            </div>
          </div>
        </div>
        <!-- trailingContent: small "+" Add files button -->
      </div>
    </div>
    <!-- OR browse button (when no files): -->
    <button>Browse files</button>
    <FileDropzoneInstructions />
  </section>
</div>
```

Key insight: chips and the "Browse files" button are **mutually exclusive** (a React ternary). When files are uploaded, the button is gone. When the button shows, there are no chips.

## Approaches Tried

### 1. Sibling CSS selector (`~ *`)
`[data-testid="stFileUploadDropzone"] ~ *` - Failed because:
- Typo: actual attribute is `stFileUploaderDropzone` (with "er")
- Even with correct name, chips are children not siblings

### 2. Direct chip hiding
`[data-testid="stFileChips"] { display: none }` - Hid the chips successfully, but left an empty gray dropzone with no visible "Browse files" button (since Streamlit doesn't render it when files exist).

### 3. Chip hiding + st.rerun()
Added `st.session_state.uploader_key += 1; st.rerun()` after queuing files to reset the widget back to "Browse files" state. This worked but introduced a 5-10 second unresponsive delay on mobile while the page re-rendered.

### 4. Reverted to original (current state)
Restored the original CSS selectors that target old `data-testid` values. These selectors don't match anything in current Streamlit, so the native chips show through. Acceptable tradeoff.

## Recommended Future Approaches

1. **CSS `::after` pseudo-element**: Hide `stFileChips` and add `::after` content on the dropzone to show "Add more files" text. The dropzone is still fully clickable/droppable via `getRootProps()`. Needs testing on mobile.

2. **JavaScript injection**: Use `st.components.v1.html()` to inject JS that manipulates the DOM after render - could hide chips and clone/re-insert the browse button.

3. **Streamlit update**: Monitor Streamlit releases for a built-in option to disable the native file list (`st.file_uploader` has no such parameter as of 1.53).

4. **Custom component**: Build a custom Streamlit component that wraps file upload without the native file list.

## Source Files
- `app.py` lines 439-462: `render_file_upload()` with CSS injection
- `app.py` lines 487-518: `render_file_preview()` custom thumbnail grid
- Streamlit source: `frontend/lib/src/components/widgets/FileUploader/`

## Version History
- 0.9.2: Original (issue reported)
- 0.9.3: First CSS fix attempt (sibling selector, didn't work)
- 0.9.4: Second CSS fix (stFileChips, hid chips but empty dropzone)
- 0.9.5: Added st.rerun() (worked but 5-10s mobile delay)
- 0.9.6: Reverted to original behavior (current)
