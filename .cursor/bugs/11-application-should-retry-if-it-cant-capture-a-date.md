---
github_issue: 49
---
# Application should retry if it can't capture a date.

## Working directory

`~/Desktop/receipt-ranger`

## Contents

If the application can't capture a receipt date, then the date field in the resulting table is blank, and it doesn't attempt to upload a Google sheet because it doesn't know what date to upload to. If the application in the web version can't capture a date, it should offer to retry. There should be two or three retry steps before it gives up and asks you to just enter the receipt manually. 

## Acceptance criteria
