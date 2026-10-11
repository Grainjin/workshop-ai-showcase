import type { BookingAttachment, BookingAttachmentPurpose } from "../types/booking";

const sections: { purpose: BookingAttachmentPurpose; title: string }[] = [
  { purpose: "customer_attachment", title: "Customer attachments" },
  { purpose: "arrival_evidence", title: "Arrival evidence" },
  { purpose: "completion_proof", title: "Completion proof" },
];

export function getBookingAttachmentSections(
  attachments: BookingAttachment[] = [],
  currentQuoteRevisionId: number | null = null,
) {
  const standardSections = sections.map((section) => ({
    ...section,
    attachments: attachments.filter((attachment) => attachment.purpose === section.purpose),
  }));
  const quoteAttachments = attachments.filter(
    (attachment) => attachment.purpose === "quote_attachment",
  );
  const quoteSections = [
    {
      purpose: "current_quote_attachment" as const,
      title: "Current quote attachments",
      attachments: currentQuoteRevisionId == null
        ? []
        : quoteAttachments.filter(
            (attachment) => attachment.quote_revision_id === currentQuoteRevisionId,
          ),
    },
    {
      purpose: "previous_quote_attachment" as const,
      title: "Previous quote attachments",
      attachments: quoteAttachments.filter(
        (attachment) =>
          currentQuoteRevisionId == null ||
          attachment.quote_revision_id !== currentQuoteRevisionId,
      ),
    },
  ];

  return [standardSections[0], ...quoteSections, ...standardSections.slice(1)];
}
