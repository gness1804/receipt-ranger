---
github_issue: 49
---
# Application should retry if it can't capture a date.

## Working directory

`~/Desktop/receipt-ranger`

## Contents

If the application can't capture a receipt date, then the date field in the resulting table is blank, and it doesn't attempt to upload a Google sheet because it doesn't know what date to upload to. This is a poor user experience because the user then has to enter in the entire receipt data in the Google Receipts just because a date wasn't captured, even if everything else was fine. Instead of the current behavior, I would like the following behavior. 

If the application fails to capture a date for a particular receipt, either because it couldn't find the date or the date wasn't legible, then it should do the following: 

- Retry once
- If after the retry the date is still not shown, it should still upload the receipt data to Google Sheets, but to a new tab called "Unknown Date". 

This will allow the user to only have to worry about entering in the date in Google Sheets manually, rather than having to enter in the entire recipe. If the date fails, the user will still be able to capture most of the information automatically. 

## Acceptance criteria

<!-- DONE -->
