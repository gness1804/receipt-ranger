---
github_issue: 1
---
# Build Out Mvp Of The Project

## Working directory

`~/Desktop/receipt-ranger`

## Contents

We need to build out the MVP for this project. This project is a receipt scanner that allows you to transform images of receipts into JSON and Google Sheets-compatible table output. 

The application uses BAML to extract key data from recipes. A lot of the BAML logic is already there. See baml_client/ and baml_src/.

For the MVP, the application, when run, will iterate through all of the receipt images in the folder .cursor/data/receipts. For each receipt that it finds, it will first validate that it's a valid image type. After that validation completes successfully, For each recipe, the application will run an LLM analysis of the recipe to output the relevant data. The data needed and the surrounding logic is available at baml_src/receipt.baml. 

The application will keep track of which receipts it's already looked at. And so when it iterates in the future, it will only analyze the receipts it has not looked at. The user can override this behavior and analyze all receipts by using the flag --duplicates. After each run, it will output its results in a JSON file with a list of all the receipts that were looked at. Then, the script will transform that JSON file into a Google Sheets-friendly table that can be easily copied and pasted into Google Sheets. 

| Amount | Date | (Blank space to be filled in later or manually) | Vendor | Category
|------|--------|--------|----------|
|    |      |        |        |       

Please first create a plan with steps, and let me approve the plan before doing any work. 

## Acceptance criteria

- An MVP application that takes in receipt images and emits a Google Sheets-compatible table with the data. 
- Application will use BAML to process the receipts and make sure that they're in a strict data format. (See details above.)
- The application will know which receipts it's already processed in order to not process them again, unless the user specifies that they want this behavior. 
- The application will use an LLM with BAML for the receipt processing.
- The MVP will be back-end only. Future versions will introduce a front-end and possibly other features, such as uploading a receipt directly from a front-end. But this MVP covered by this ticket will only be back-end logic. 
- The application's run will be triggered by something like `python3 main.py`. 
