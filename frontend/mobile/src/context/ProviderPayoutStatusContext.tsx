import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { getProviderSubmerchant } from "../api/marketplace";
import { useAuth } from "./AuthContext";
import type { SubmerchantStatus } from "../types/marketplace";

type ProviderPayoutStatusContextValue = {
  status: SubmerchantStatus | null;
  refresh: () => Promise<void>;
};

const ProviderPayoutStatusContext = createContext<
  ProviderPayoutStatusContextValue | null
>(null);

export function ProviderPayoutStatusProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [status, setStatus] = useState<SubmerchantStatus | null>(null);

  const refresh = useCallback(async () => {
    if (user?.role !== "provider") {
      setStatus(null);
      return;
    }

    try {
      const payoutAccount = await getProviderSubmerchant();
      setStatus(payoutAccount?.status ?? "draft");
    } catch {
      // Do not show a misleading warning when the status request itself fails.
      setStatus(null);
    }
  }, [user?.role]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(() => ({ status, refresh }), [refresh, status]);

  return (
    <ProviderPayoutStatusContext.Provider value={value}>
      {children}
    </ProviderPayoutStatusContext.Provider>
  );
}

export function useProviderPayoutStatus() {
  const context = useContext(ProviderPayoutStatusContext);

  if (!context) {
    throw new Error(
      "useProviderPayoutStatus must be used inside ProviderPayoutStatusProvider",
    );
  }

  return context;
}
