# Receipt Ranger

## Introduction

Receipt Ranger is a tool for managing receipts and invoices. It is designed to help you keep track of your expenses and income. Its core functionality should include ingesting images of receipts and using an LLM and BAML to extract key information. The BAML Receipt class should look something like this: 

```baml
class Receipt {
    id: string; # For internal reference and programmatic use, would not go into V1 output table. 
    date: string;
    vendor: string;
    amount: number;
    category: string; 
    paymentMethod: string; # For internal reference, would not go into V1 output table. 
    cardNumber: string | null; # For internal reference, would not go into V1 output table. 
}
```

The output of the LLM run will be structured data in the format described above. The application will then take this data and present it in a format that is easy to copy over to a Google Sheet. This format should not be a code block, but rather should be more of a table that you can easily copy and paste into the Google Sheets spreadsheet that we're using to keep track of expenses. 

Application should also keep track of such things as accounting for duplicates, ensuring that each receipt is only processed once, and maintaining a record of all processed receipts for future reference.

The table might look like this (This is only provisional, and the order would probably need to be changed.):

| Date | Vendor | Amount | Category |
|------|--------|--------|----------|
|    |      |        |        |          |                |             |

## CFS Initialization

This directory was initialized using the Cursor File Structure (CFS) CLI.

### Categories

- **rules/** - Rules used by Cursor (automatically read by Cursor agents)
- **research/** - Research-related documents
- **bugs/** - Bug investigation and fix instructions
- **features/** - Feature development documents
- **refactors/** - Refactoring-related documents
- **docs/** - Documentation creation instructions
- **progress/** - Progress tracking and handoff documents
- **qa/** - Testing and QA documents
- **tmp/** - Temporary files for Cursor agent use

### Usage

Use the `cfs` CLI tool to manage documents in these categories.

*NOTE: The command `cfs instructions` has two aliases: `cfs i` and `cfs instr`.*

#### Quick Start

```bash
# Create a new bug investigation document
cfs instructions bugs create

# Edit a document
cfs instructions bugs edit 1

# View all documents
cfs instructions view

# Create a rules document
cfs rules create
```

For help: `cfs --help`
