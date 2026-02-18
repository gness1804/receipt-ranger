---
github_issue: 33
---
# Adjust the date formatting to match what the Graham and Sarah Expenses spreadsheet accepts.

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Right now, the output of Receipt Ranger to Google Sheets formats the dates as follows: 

02/05/2026

However, the Graham and Sarah Expenses spreadsheet expects the following format:

2/6/2026

I need to reconcile the date formatting between these two sources. I favor adjusting the receipt ranger output to match the output of the Graham and Sarah expenses spreadsheet. 

Looking more closely, the exact date format omitted by Receipt Ranger to Google Sheets is '02/12/2026.

Notice the leading quote marker. I assume this is there to force the spreadsheet to preserve the leading zero. But as noted above, my main spreadsheet (the one where I actually use my receipts data) does not use leading zeros. So that leading quote mark or apostrophe should not be used when Receipt Ranger outputs dates. 

## Acceptance criteria
