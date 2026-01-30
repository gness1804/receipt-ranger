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
    id string @description("For internal reference and programmatic use, would not go into V1 output table.")
    amount float @description("The total amount of the receipt. Include all tips, taxes, etc. in the amount.")
    date string @description("The date of the receipt. Format should be MM/DD/YYYY.")
    vendor string @description("The vendor of the receipt.")
    category ReceiptCategory[] @description("The canonical categories for the receipt. Use only values from ReceiptCategory. If multiple categories are present, list them all. If you can't determine a category, present an empty list.")
    paymentMethod string[] @description("The method of payment used for the receipt. Examples could include: Cash, Card, Check, Gift Card, etc. If multiple payment methods are present, list them all. In the rare case when you can't determine a payment method, just present an empty list.")
    excludeFromTable bool @description("Whether to exclude this receipt from the output table. Default is false. Should only be true if the receipt meets the exclusion conditions described in input documents.")
    exclusionReason string @description("If excludeFromTable is true, provide a brief explanation of why this receipt was excluded. If excludeFromTable is false, this should be an empty string.")
}

function ExtractReceiptFromImage(image: image, exclusionCriteria: string) -> Receipt {
    client "CustomSonnet4"
    prompt #"
        {{ _.role("user") }}
        Extract the receipt from the following image. Format the date as MM/DD/YYYY. If the amount is not a whole number, format it as a decimal. For instance, $10.50 should be formatted as 10.50. If the amount is not present, set the amount to 0.00. If the vendor is not present, set the vendor to "Unknown". Use only ReceiptCategory values for category. If the category is not present, set the category to an empty list. If the payment method is not present, set the payment method to an empty list.

        Do not set the date field to anything after the current date. If you are unable to determine the date, then just say "unknown" for the date field instead of trying to guess or putting a date that has not happened yet.

        NOTE: Do not exclude a receipt from the table because of its date. Only exclude a receipt from the table due to the criteria described below.

        EXCLUSION CRITERIA:
        After extracting the receipt data, evaluate whether this receipt should be excluded from the output table based on the following criteria. If any of these conditions are met, set excludeFromTable to true and provide a brief exclusionReason. If no exclusion criteria are provided or none match, set excludeFromTable to false and exclusionReason to an empty string. Do not exclude a receipt from the table for any reason other than those explicitly stated below.

        {{ exclusionCriteria }}

        {{ image }}

        {{ ctx.output_format }}
    "#
}

test ExtractReceiptFromImageTest {
  functions [ExtractReceiptFromImage]
  args {
    image {
        file "taco_cabana.jpeg"
    }
    exclusionCriteria "No exclusion criteria for this test."
  }
}
