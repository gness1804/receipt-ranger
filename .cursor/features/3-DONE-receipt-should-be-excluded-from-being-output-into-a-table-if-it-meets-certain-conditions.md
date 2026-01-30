---
github_issue: 5
---
# Receipt Should Be Excluded From Being Output Into A Table If It Meets Certain Conditions

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Right now, every receipt that gets created is automatically output into a table. But I've created a new property on the receipt class called excludeFromTable. It's a Boolean, and if it's marked as true, then the application should not output it to a table but instead should output a warning message saying that the receipt was excluded from the table and the reason. These excluded receipts should still appear in the JSON file recording receipts and in the hashes. The deduplication logic should still apply to it; it just shouldn't be displayed in the table. 

The application should tell the LLM, when it's evaluating the receipt, how to evaluate the exclude from table logic. The exclude from table logic should exist in another document, which I want to keep un-versioned because it has some sensitive information. For example, certain credit card numbers should be excluded from the table. Want to be able to use an unversioned document and connect it with the logic of how to interpret a table. Is to be fed into the LLM call via system prompt or something like that. 

## Acceptance criteria

- The LLM, when evaluating each recipe image, will be able to judge whether the recipe should be excluded from the table based on criteria that's fed to it via an unversion document. 
- The LLM will assign a value to this exclude_from_table property of a boolean. 
- Regardless of whether a recipe is marked as to be excluded from the table, it should still be included in deduplication logic and hashing.

<!-- DONE -->
