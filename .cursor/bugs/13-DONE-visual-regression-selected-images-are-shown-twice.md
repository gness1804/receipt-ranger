---
github_issue: 54
---
# Visual Regression: Selected images are shown twice.

## Working directory

`~/conductor/workspaces/receipt-ranger/caracas`

## Contents

The site is supposed to only show the selected receipts once in the view below the file selector with the thumbnails. But as can be seen in the screenshot, the smaller icons of the same images are shown in the file selection area as well. The file selection area also looks different than before. Instead of an upload button, there's a little cross that's very close to the touch area of one of the Xs to delete an uploaded screenshot. This is a poor UI, and I'm not sure how it got introduced, but we need to go back to how things were, where there's only the thumbnail showing up and there's a larger file uploader. 

I remember specifically hiding the selected image tiles, so I'm not sure why they're showing up again. I also don't know where the little cross came from. But this needs to be fixed. 

<img width="1436" height="711" alt="Image" src="https://github.com/user-attachments/assets/687701bb-ee7e-466b-a2ab-0947fea5b81f" />

## Acceptance criteria

<!-- DONE -->
