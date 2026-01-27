class Receipt {
    id string @description("For internal reference and programmatic use, would not go into V1 output table.")
    amount float @description("The total amount of the receipt. Include all tips, taxes, etc. in the amount.")
    date string @description("The date of the receipt. Format should be MM/DD/YYYY.")
    vendor string @description("The vendor of the receipt.")
    category string[] @description("The category of the receipt. Examples could include: Food/restaurants, Clothing, Entertainment, Housing, etc. If multiple categories are present, list them all. In the rare case when you can't determine a category, just present an empty list.")   
    paymentMethod string[] @description("The method of payment used for the receipt. Examples could include: Cash, Card, Check, Gift Card, etc. If multiple payment methods are present, list them all. In the rare case when you can't determine a payment method, just present an empty list.")
}

function ExtractReceiptFromImage(image: image) -> Receipt {
    client "CustomGPT5Mini" // TODO: Change to CustomSonnet4 for production
    prompt #"
        {{ _.role("user") }}
        Extract the receipt from the following image. Format the date as MM/DD/YYYY. If the amount is not a whole number, format it as a decimal. For instance, $10.50 should be formatted as 10.50. If the amount is not present, set the amount to 0.00. If the vendor is not present, set the vendor to "Unknown". If the category is not present, set the category to an empty list. If the payment method is not present, set the payment method to an empty list.
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
  }
}
