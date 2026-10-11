import type { BookingUploadFile } from "../types/booking";

type QuoteFields = {
  quote_amount: number;
  quote_message: string | null;
  expected_service_amount?: number;
  visit_fee_amount?: number;
};

export async function buildBookingQuoteBody(
  fields: QuoteFields,
  files: BookingUploadFile[],
  appendFile: (body: FormData, field: string, file: BookingUploadFile) => Promise<void>,
): Promise<QuoteFields | FormData> {
  if (!files.length) return fields;
  const body = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    if (value != null) body.append(name, String(value));
  }
  for (const file of files) await appendFile(body, "quote_files", file);
  return body;
}
