enum ReceiptCategory {
    FOOD_RESTAURANTS @alias("Food & Restaurants")
    GROCERIES @alias("Groceries")
    TRANSPORTATION @alias("Transportation")
    TRAVEL @alias("Travel")
    LODGING @alias("Lodging")
    UTILITIES @alias("Utilities")
    HOUSING_RENT @alias("Housing & Rent")
    HEALTH_MEDICAL @alias("Health & Medical")
    INSURANCE @alias("Insurance")
    ENTERTAINMENT_RECREATION @alias("Entertainment & Recreation")
    CLOTHING_SHOES @alias("Clothing & Shoes")
    ELECTRONICS_GADGETS @alias("Electronics & Gadgets")
    HOME_GARDEN @alias("Home & Garden")
    OFFICE_SUPPLIES @alias("Office & Supplies")
    EDUCATION @alias("Education")
    GIFTS_DONATIONS @alias("Gifts & Donations")
    SUBSCRIPTIONS_MEMBERSHIPS @alias("Subscriptions & Memberships")
    FEES_SERVICES @alias("Fees & Services")
    TAXES @alias("Taxes")
    CHILDCARE @alias("Childcare")
    PET_CARE @alias("Pet Care")
    PERSONAL_CARE @alias("Personal Care")
    OTHER @alias("Other")
}

class Receipt {
    isValidReceipt bool @description("Whether this image is a valid receipt. Set to true only if the image clearly shows a receipt, invoice, or similar purchase document. Set to false for non-receipt images like photos, screenshots, memes, documents, etc.")
    validationError string @description("If isValidReceipt is false, provide a brief explanation of why this is not a valid receipt (e.g., 'Image shows a landscape photo, not a receipt'). If isValidReceipt is true, this should be an empty string.")
    id string @description("For internal reference and programmatic use, would not go into V1 output table.")
    amount float @description("The total amount of the receipt. Include all tips, taxes, etc. in the amount. If you cannot determine the amount, just put zero.")
    date string @description("The date of the receipt. Format should be MM/DD/YYYY. If you cannot determine the date, just put an empty string.")
    vendor string @description("The vendor of the receipt. If you cannot determine the vendor, just put an empty string.")
    category ReceiptCategory[] @description("The canonical categories for the receipt. Use only values from ReceiptCategory. If multiple categories are present, list them all. If you can't determine a category, present an empty list.")
    paymentMethod string[] @description("The method of payment used for the receipt. Examples could include: Cash, Card, Check, Gift Card, etc. If multiple payment methods are present, list them all. In the rare case when you can't determine a payment method, just present an empty list.")
    excludeFromTable bool @description("Whether to exclude this receipt from the output table. Default is false. Should only be true if the receipt meets the exclusion conditions described in input documents.")
    exclusionReason string @description("If excludeFromTable is true, provide a brief explanation of why this receipt was excluded. If excludeFromTable is false, this should be an empty string.")
}

// Shared prompt template for receipt extraction
template_string ReceiptExtractionPrompt(image: image, exclusionCriteria: string, currentDate: string) #"
    {{ _.role("user") }}
    Analyze the following image and extract receipt information if it is a valid receipt.

    VALIDATION RULES (CHECK FIRST):
    Before extracting any data, determine if this image is a valid receipt:
    - A valid receipt is a document showing a purchase transaction (receipt, invoice, bill, purchase confirmation)
    - Set isValidReceipt to TRUE only if the image clearly shows a receipt or similar purchase document
    - Set isValidReceipt to FALSE for: photos, screenshots of apps/websites (unless showing a receipt), memes, random documents, non-receipt images, blank images, or unclear/unreadable images
    - If isValidReceipt is FALSE, set validationError to explain why, and leave all other fields at their default values (empty strings, zero, empty arrays, false)

    {{ image }}

    If the image IS a valid receipt, proceed with extraction:

    EXTRACTION RULES:
    - If the amount is not a whole number, format it as a decimal (e.g., $10.50 → 10.50)
    - Use only ReceiptCategory values for category
    - Today's date is {{ currentDate }}. If the receipt date appears to be after {{ currentDate }}, leave the date field as an empty string
    - If you cannot determine the date, leave it as an empty string. Do not guess.

    EXCLUSION CRITERIA (READ CAREFULLY):
    The excludeFromTable field should ONLY be set to true if the receipt matches one of the criteria listed below. If no criteria are listed, or if the receipt does not match any listed criteria, you MUST set excludeFromTable to false.

    IMPORTANT: The following are NOT valid reasons to exclude a receipt:
    - The receipt's date (past, present, or future dates are all acceptable)
    - Missing or unclear information on the receipt
    - The receipt's amount, vendor, or category

    The ONLY valid exclusion criteria are:
    {{ exclusionCriteria }}

    If the above criteria section is empty or says "No exclusion criteria", then set excludeFromTable to false and exclusionReason to an empty string.

    {{ ctx.output_format }}
"#

// Anthropic version (Claude Sonnet 4)
function ExtractReceiptFromImage(image: image, exclusionCriteria: string, currentDate: string) -> Receipt {
    client "CustomSonnet4"
    prompt #"{{ ReceiptExtractionPrompt(image, exclusionCriteria, currentDate) }}"#
}

// OpenAI version (GPT-5 Mini)
function ExtractReceiptFromImageOpenAI(image: image, exclusionCriteria: string, currentDate: string) -> Receipt {
    client "CustomGPT5Mini"
    prompt #"{{ ReceiptExtractionPrompt(image, exclusionCriteria, currentDate) }}"#
}

test ExtractReceiptFromImageTest {
  functions [ExtractReceiptFromImage]
  args {
    image {
        file "taco_cabana.jpeg"
    }
    exclusionCriteria "No exclusion criteria for this test."
    currentDate "01/31/2026"
  }
}
