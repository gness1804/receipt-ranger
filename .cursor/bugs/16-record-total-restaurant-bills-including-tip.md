---
github_issue: 74
---
# Record total restaurant bills including tip

## Working directory

`~/Desktop/receipt-ranger`

## Contents

The application sometimes misreads restaurant receipts to include the pre-tip total as the final amount. Often, with a restaurant receipt, below the final printed amount, there will be a handwritten tip and then a handwritten total. It seems like Receipt Ranger often ignores these. The application's instructions and other relevant parts need to be changed to ensure that the application, when it reads restaurant receipts, always records the final amount, including the tip. 

Acceptance criteria 
- When reading a restaurant receipt with the tip, the application will always record the final post-tip amount as the total amount for that receipt.

## Acceptance criteria
