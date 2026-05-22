---
github_issue: 72
---
# App does not save API key

## Working directory

`~/Desktop/receipt-ranger`

## Contents

When I enter in an API key successfully and then enter a receipt and process it, the application works as expected. But if I then refresh the page, it asks for an API key again. The application is supposed to save a hash of the API key in local storage. This worked until recently. Now, when I use the application, the local key saving no longer works. We need to fix this. 


## Acceptance criteria

- [ ] When the application has successfully received an API key and then you refresh the page or return to the application later, the API key should still be saved.

<!-- DONE -->
