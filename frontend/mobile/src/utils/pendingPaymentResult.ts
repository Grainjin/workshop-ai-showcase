import AsyncStorage from "@react-native-async-storage/async-storage";

import type { RootStackParamList } from "../navigation/types";

const PENDING_PAYMENT_RESULT_KEY = "workshop_ai_pending_payment_result";

type PendingPaymentResult = RootStackParamList["PaymentResult"];

export async function savePendingPaymentResult(
  params: PendingPaymentResult,
) {
  await AsyncStorage.setItem(
    PENDING_PAYMENT_RESULT_KEY,
    JSON.stringify(params),
  );
}

export async function consumePendingPaymentResult(): Promise<PendingPaymentResult | null> {
  const stored = await AsyncStorage.getItem(PENDING_PAYMENT_RESULT_KEY);
  if (!stored) {
    return null;
  }

  await AsyncStorage.removeItem(PENDING_PAYMENT_RESULT_KEY);
  try {
    return JSON.parse(stored) as PendingPaymentResult;
  } catch {
    return null;
  }
}
