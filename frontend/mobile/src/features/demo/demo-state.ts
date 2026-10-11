import type { DemoRole } from "../../types/auth";

export type DemoLoginState = {
  pendingRole: DemoRole | null;
  errorMessage: string;
};

type DemoLoginEvent =
  | { type: "start"; role: DemoRole }
  | { type: "success" }
  | { type: "failure" };

const roleOptions: { role: DemoRole; label: string; purpose: string }[] = [
  { role: "customer", label: "Customer", purpose: "Find providers and book a service." },
  { role: "provider", label: "Provider", purpose: "Manage requests, quotes, and appointments." },
  { role: "admin", label: "Admin", purpose: "Explore platform management and reviews." },
];

export function createDemoLoginState(): DemoLoginState {
  return { pendingRole: null, errorMessage: "" };
}

export function reduceDemoLogin(
  state: DemoLoginState,
  event: DemoLoginEvent,
): DemoLoginState {
  if (event.type === "start") {
    return state.pendingRole
      ? state
      : { pendingRole: event.role, errorMessage: "" };
  }

  return {
    pendingRole: null,
    errorMessage: event.type === "failure"
      ? "Demo sign-in is unavailable. Please try again."
      : "",
  };
}

export function getDemoRoleButtons(enabled: boolean, state: DemoLoginState) {
  return enabled ? roleOptions.map((option) => ({
    ...option,
    accessibilityLabel: `Try the ${option.label} demo. ${option.purpose}`,
    disabled: state.pendingRole !== null,
    isLoading: state.pendingRole === option.role,
  })) : [];
}
