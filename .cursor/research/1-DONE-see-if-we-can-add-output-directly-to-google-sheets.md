---
github_issue: 4
---
# See If We Can Add Output Directly To Google Sheets

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Currently, the app outputs receipt data in a TSV that's suitable to copy and paste into Google Sheets. But it would be ideal if we can add the receipt data to Google Sheets directly. We need to research of this is possible and if so, what we need. 

This feature would need to first check if there are any duplicates. First, check if the entry is already in the Google Sheet, and only add the entry if it isn't. Do this for each new entry. The application would probably iterate through either the JSON or the TSV file with all receipt records, and then add them to the Google Sheet accordingly. 

This would also be good to break down by month. That is a different Google sheet for November, December, January, etc. And place the entries in their appropriate sheet.

<!-- DONE -->
