import { ScreenContainer } from "../components/ScreenContainer";
import { PlaceholderPanel } from "../components/PlaceholderPanel";

// Notification preferences belong under Account; the inbox has its own entry.
// This demo displays a placeholder because preference controls are unavailable.
export function NotificationSettingsScreen() {
  return (
    <ScreenContainer>
      <PlaceholderPanel
        title="Notification settings"
        description="Choose which updates reach you by push and email. Coming soon — this demo sends every notification."
      />
    </ScreenContainer>
  );
}
