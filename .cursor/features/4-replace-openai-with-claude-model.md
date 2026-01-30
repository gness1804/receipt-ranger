---
github_issue:
---
# Replace OpenAI With Claude Model

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Replace the OpenAI LLM currently being used to transform receipt images with a Claude model.

## Acceptance criteria

- The BAML client configuration in `baml_src/clients.baml` is updated to use a Claude model instead of OpenAI.
- The receipt extraction function in `baml_src/receipt.baml` is updated to use the new Claude client.
- Receipt processing continues to work correctly with the new model.
