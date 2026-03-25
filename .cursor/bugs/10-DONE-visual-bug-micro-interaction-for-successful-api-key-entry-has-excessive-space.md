---
github_issue: 44
---
# Visual bug: micro interaction for successful API key entry has excessive space.

## Working directory

`~/Desktop/receipt-ranger`

## Contents

When you go to the app and you successfully enter in an API key, it gives you a micro interaction, which is a green box saying "API key configured". There's too much spacing around the box; the spacing needs to be removed, and the green box probably needs to be centered. See the screenshot for what's broken. 

<img width="1889" height="1005" alt="Image" src="https://github.com/user-attachments/assets/3b526a62-2142-4d88-b40e-3708aa996b30" />

## Acceptance criteria

## Status: Resolved

### Root cause

Streamlit's `stVerticalBlock` flex container inside columns uses a CSS `gap` property that created excessive vertical spacing between the text input and the success message.

### Fix

Added a targeted CSS override via `st.markdown(unsafe_allow_html=True)` that sets `gap: 0 !important` on `stVerticalBlock` elements within columns inside the API Configuration expander.

<!-- DONE -->
