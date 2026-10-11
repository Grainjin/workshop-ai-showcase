export const CURRENCY_CODE = "TRY";

export function formatMoney(value: number | string | null | undefined) {
  if (value == null || value === "") {
    return "—";
  }

  const amount = Number(value);
  if (Number.isNaN(amount)) {
    return "—";
  }

  return `${amount.toFixed(2)} ${CURRENCY_CODE}`;
}

export function formatPayLabel(value: number | string | null | undefined) {
  if (value == null || value === "") {
    return "Pay";
  }

  return `Pay ${formatMoney(value)}`;
}
