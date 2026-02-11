---
github_issue: 24
---
# Figure out better way to persist receipt data per user

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Right now, we have the file processed_receipts.json Which contains a record of receipts that were run. This worked fine in a localhost application when it was just me running receipts. But if multiple users use my application, this file could get crowded. I think we have a few options:

1. Keep this file. Since it's Git-ignored, it will be different on the EC2 vs localhost. We could add a feature where the JSON on this file has a field for the individual user, and that way receipts will be mapped to individual users in this file. This would make for a big file, but it would keep individual users separate. The application's logic would also have to change to accommodate this change in this file. 
2. Remove this file and don't check for duplicates. This is the easiest solution, but it might be problematic. But since it's a pretty simple app, persisting a record of receipts might not be necessary. The application has separate logic to check for duplicates in Google Sheets when I try to add a receipt to Google Sheets, and this logic should stay. We need to take a look at how exactly this file processed_receipts.json is being used. That will help us determine whether we need to keep it or not. 
3. This third solution probably wouldn't happen until a later version of the application. But if we ever add user logins, we could use something like DynamoDB or another more permanent solution to store user records to check for duplicates. This enhanced application can also do things like keep a record of the history of different users' spending and receipts, and do things like calculate total spending by category, etc. But right now, we're not going to worry about those things. Just a note about what I might implement moving forward, sometime in the future. 

Now we will go with either number one or number two. We need to look at what this file is doing and assess whether it's worth it to keep the file and if so, whether it makes sense to try to add a field for user for each receipt.  


## Acceptance criteria

- We need to figure out which of these solutions makes the most sense and implement it. 
- The application will have a logical implementation regarding tracking duplicates if we decide to keep this feature at all. 
