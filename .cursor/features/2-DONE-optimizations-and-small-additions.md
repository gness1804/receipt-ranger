---
github_issue: 2
---
# Optimizations And Small Additions

## Working directory

`~/Desktop/receipt-ranger`

## Contents

We should add the following optimizations in small additions:

- An option to generate a table from existing processed receipts without regenerating. RIght now, the only way to show a table of the process receipts. We want to be able to show tables without doing this, for receipts that have already been processed.
-Along the same lines, we want an option to print out a TSV table of all receipts by calendar month, vendor, amount (over or under a certain amount), and category (Food/Restaurants, Clothes, etc). Also include an option to print out a TSV table of ALL receipts ever recorded. (This is not reprocessing all of the receipts, but merely printing out a table of all of them.) 
- Right now, it seems like every time I generate new receipts, it overrides the output table. Instead, every time I generate receipts, I want to create a new output table with a timestamp. Both the JSON on the TSV. So the files would be `receipts-{timestamp}.json` and `receipts-{timestamp).tsv`. 

## Acceptance criteria

- Implement the above.
- The tables should make sure to not have any duplicates in them.

<!-- DONE -->
