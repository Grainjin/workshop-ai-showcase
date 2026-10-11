const assert = require("node:assert/strict");
const test = require("node:test");

const {
  canCustomerCancelAfterVisit,
  canCustomerRequestRefund,
  shouldShowBookingInChat,
} = require("../../../.test-build/utils/bookingActions.js");

test("awaiting confirmation offers refund without cancel and remains in Chat", () => {
  const booking = {
    status: "awaiting_confirmation",
    current_refund_request: null,
  };
  const payment = { status: "paid" };

  assert.equal(canCustomerCancelAfterVisit(booking.status, payment), false);
  assert.equal(canCustomerRequestRefund(booking, payment), true);
  assert.equal(shouldShowBookingInChat(booking.status), true);
});

test("a customer-confirmed booking no longer appears as the active Chat booking", () => {
  assert.equal(shouldShowBookingInChat("completed"), false);
});

test("an active visit remains visible in Chat and supports the existing actions", () => {
  const booking = {
    status: "provider_arrived",
    current_refund_request: null,
  };
  const payment = { status: "paid" };

  assert.equal(canCustomerCancelAfterVisit(booking.status, payment), true);
  assert.equal(canCustomerRequestRefund(booking, payment), true);
  assert.equal(shouldShowBookingInChat(booking.status), true);
});
