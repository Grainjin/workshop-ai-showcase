export function getDefaultServiceCategory(values: string[]) {
  return values.length === 1 ? values[0] : "";
}

export function isCanonicalServiceSelection(value: string, values: string[]) {
  return values.includes(value);
}
