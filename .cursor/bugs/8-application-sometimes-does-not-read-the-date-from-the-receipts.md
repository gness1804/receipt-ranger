---
github_issue: 38
---
# Application sometimes does not read the date from the receipts.

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Sometimes when processing a receipt, the application fails to read the date, even though the date is clearly stated on the receipt. An example receipt that failed in this way is below:

![Image](https://github.com/user-attachments/assets/709f2334-4f89-4c60-ae6b-9f9e6fa9abaf)

Without loosening the receipt rules that we have in place and allowing the application to make silly mistakes like estimating dates that are in the future, we need to try to improve the application's accuracy at interpreting the date for the receipts. 

## Acceptance criteria
