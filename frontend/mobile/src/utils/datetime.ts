export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "—";
  }

  const date = parseDateTime(value);
  if (!date) {
    return value;
  }

  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatShortDateTime(value: string | null | undefined) {
  if (!value) {
    return "";
  }

  const date = parseDateTime(value);
  if (!date) {
    return value.replace("T", " ").slice(0, 16);
  }

  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateTimeInput(date: Date) {
  return `${toDatetimeLocalValue(date)}:00`;
}

export function toEditableDateTime(value: string | null | undefined) {
  if (!value) {
    return "";
  }

  const date = parseDateTime(value);
  if (!date) {
    return value.replace("Z", "").slice(0, 19);
  }

  return formatDateTimeInput(date);
}

export function toDatetimeLocalValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  return `${year}-${month}-${day}T${hour}:${minute}`;
}

export function fromDatetimeLocalValue(value: string) {
  if (!value) {
    return "";
  }

  return value.length === 16 ? `${value}:00` : value;
}

export function parseDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date;
}
