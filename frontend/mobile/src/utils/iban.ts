export function isValidTurkishIban(value: string) {
  if (!/^TR\d{24}$/.test(value)) {
    return false;
  }

  // Convert the country code after moving it behind the check digits.
  // Turkish IBAN letters use T=29 and R=27 in the checksum calculation.
  const rearranged = `${value.slice(4)}2927${value.slice(2, 4)}`;
  let remainder = 0;
  for (const character of rearranged) {
    remainder = (remainder * 10 + Number(character)) % 97;
  }
  return remainder === 1;
}
