import { useCallback, useState } from "react";

import { ConfirmationModal } from "../components/ConfirmationModal";

type ConfirmationRequest = {
  confirmLabel: string;
  message: string;
  onConfirm: () => void;
  title: string;
};

export function useConfirmation() {
  const [request, setRequest] = useState<ConfirmationRequest | null>(null);

  const requestConfirmation = useCallback((next: ConfirmationRequest) => {
    setRequest(next);
  }, []);

  const dismissConfirmation = useCallback(() => {
    setRequest(null);
  }, []);

  const confirm = useCallback(() => {
    if (!request) {
      return;
    }

    const onConfirm = request.onConfirm;
    setRequest(null);
    onConfirm();
  }, [request]);

  return {
    confirmationModal: (
      <ConfirmationModal
        confirmLabel={request?.confirmLabel || "Confirm"}
        message={request?.message || ""}
        onCancel={dismissConfirmation}
        onConfirm={confirm}
        title={request?.title || "Confirm action"}
        visible={Boolean(request)}
      />
    ),
    requestConfirmation,
  };
}
