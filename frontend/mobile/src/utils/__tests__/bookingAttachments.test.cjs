const test = require("node:test");
const assert = require("node:assert/strict");
const { getBookingAttachmentSections } = require("../../../.test-build/utils/bookingAttachments.js");

test("groups same-uploader and same-name files by server purpose, preserving every file", () => {
  const attachments = [
    { id: 1, purpose: "customer_attachment", uploaded_by_user_id: 10, original_file_name: "photo.png" },
    { id: 2, purpose: "arrival_evidence", uploaded_by_user_id: 20, original_file_name: "photo.png" },
    { id: 3, purpose: "completion_proof", uploaded_by_user_id: 20, original_file_name: "photo.png" },
    { id: 4, purpose: "customer_attachment", uploaded_by_user_id: 10, original_file_name: "extra.pdf" },
  ];
  const sections = getBookingAttachmentSections(attachments);
  assert.deepEqual(sections.map(({ title }) => title), [
    "Customer attachments", "Current quote attachments", "Previous quote attachments",
    "Arrival evidence", "Completion proof",
  ]);
  assert.deepEqual(sections.map(({ attachments }) => attachments.map(({ id }) => id)), [
    [1, 4], [], [], [2], [3],
  ]);
  assert.equal(attachments.length, 4);
});

test("missing attachments produce empty sections without requiring provider profile or status", () => {
  assert.deepEqual(
    getBookingAttachmentSections().map(({ attachments }) => attachments),
    [[], [], [], [], []],
  );
});

test("groups all earlier visit and final quote files as previous, without numbered cards", () => {
  const attachments = [
    { id: 1, purpose: "quote_attachment", quote_revision_id: 10 },
    { id: 2, purpose: "quote_attachment", quote_revision_id: 11 },
    { id: 3, purpose: "quote_attachment", quote_revision_id: 12 },
  ];
  const sections = getBookingAttachmentSections(attachments, 12);
  assert.deepEqual(sections[1].attachments.map(({ id }) => id), [3]);
  assert.deepEqual(sections[2].attachments.map(({ id }) => id), [1, 2]);
});

test("decline moves the last files to previous; a new quote without files does not reuse them", () => {
  const attachments = [
    { id: 1, purpose: "quote_attachment", quote_revision_id: 10 },
    { id: 2, purpose: "quote_attachment", quote_revision_id: 11 },
  ];
  const afterDecline = getBookingAttachmentSections(attachments, null);
  assert.deepEqual(afterDecline[1].attachments, []);
  assert.deepEqual(afterDecline[2].attachments.map(({ id }) => id), [1, 2]);
  const afterNoFileRequote = getBookingAttachmentSections(attachments, 12);
  assert.deepEqual(afterNoFileRequote[1].attachments, []);
  assert.deepEqual(afterNoFileRequote[2].attachments.map(({ id }) => id), [1, 2]);
});
