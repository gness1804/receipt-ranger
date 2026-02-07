---
github_issue: 21
---
# Successfully uploading a receipt to the application in production causes an error message.

## Working directory

`~/Desktop/receipt-ranger`

## Contents

When you upload a receipt to the application after entering in a valid API key, the upload succeeds partially. It outputs a table onto the web page; however a red error message appears instead of generating the CSV and TSV files. This needs to be fixed. 

See the attached screenshot. This appears to be a permissions issue. Probably some permission needs to be changed to allow the application to write to the file noted in the error message. 

![image](https://github.com/user-attachments/assets/06cb7f39-5b25-4816-9018-c602a53c667b)

## Acceptance criteria

<!-- DONE -->
