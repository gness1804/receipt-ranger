---
github_issue: 14
---
# Build Out The Frontend

## Working directory

`~/Desktop/receipt-ranger`

## Contents

We need to build a front-end for this application. The front-end should consist of the following components: 
- An attractive interface with the title of the application. 
- A place for users to upload an image file. This will be where they upload receipts. 
- Standard error handling for image uploads. 
- A submit button where the user submits receipts. Users should be able to upload one or multiple receipts at a time. 
- Users should be able to remove selected receipts for processing by clicking on an 'X' button. Like when you attach a file to a ChatGPT chat but then decide not to use the file, you can get rid of the file before submitting it to ChatGPT. 
- Upon submission, the application should process the receipts. 
- The application should also automatically add the sheets to Google Sheets if they don't already exist there. So the user pressing the input button would be something similar to `python3 main.py && python3 main.py --upload-sheets`. Except that pressing the submit button would only process the reciepts that the user has submitted.  
- If any of the user-submitted receipts already exist in Google Sheets, the user should be notified of this. The application should be smart enough to know whether a given user-submitted receipt already exists in Google Sheets. 
- Applications should use the existing Google Sheets integration, but upgrade where appropriate. 
- We need to solve the problem of how to handle Anthropic/API key processing. For a local application, this shouldn't be an issue since it's just running on my computer and I'm using my own API key. But when the application is actually running in production, we will need to figure out how best to handle the API key problem so that users can't spam my API key. 
- The front-end technology used should be compatible with Python and, if possible, live in this same repo. 
- Please show a detailed plan of how you will tackle this before starting any work.

<!-- DONE -->
