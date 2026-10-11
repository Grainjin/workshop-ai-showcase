import { BookingAttachmentGallery } from "./BookingAttachmentGallery";
import type { BookingDetail } from "../types/booking";

type CompletionProofGalleryProps = {
  booking: BookingDetail;
};

export function CompletionProofGallery({ booking }: CompletionProofGalleryProps) {
  const proofFiles = (booking.attachments ?? []).filter(
    (attachment) => attachment.purpose === "completion_proof",
  );

  return <BookingAttachmentGallery attachments={proofFiles} title="Completion proof" />;
}
