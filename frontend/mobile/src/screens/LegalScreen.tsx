import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { StyleSheet, Text, View } from "react-native";

import { ScreenContainer } from "../components/ScreenContainer";
import type { LegalDocument, RootStackParamList } from "../navigation/types";
import { colors, radius, spacing } from "../theme/theme";

// Demo legal text only. The register checkbox links here with
// navigation.navigate("Legal", { document: "terms" }).
export const LEGAL_DOCUMENTS: Record<
  LegalDocument,
  { title: string; sections: { heading: string; body: string }[] }
> = {
  privacy: {
    title: "Privacy Policy",
    sections: [
      {
        heading: "What we collect",
        body: "Your name, email, role, and the details you add to bookings, chats, and your profile.",
      },
      {
        heading: "How we use it",
        body: "To match customers with providers, run bookings and payments, and send notifications about your requests.",
      },
      {
        heading: "Who can see it",
        body: "The customer and provider on a booking see each other's name and booking details. We do not sell your data.",
      },
      {
        heading: "Your choices",
        body: "You can edit your profile at any time from Account. Contact support to ask for your account to be removed.",
      },
    ],
  },
  terms: {
    title: "Terms of Use",
    sections: [
      {
        heading: "Using Workshop AI",
        body: "Workshop AI connects customers with local service providers. You are responsible for the accuracy of what you post.",
      },
      {
        heading: "Bookings and payments",
        body: "A booking is an agreement between the customer and the provider. Refund requests follow the in-app refund process.",
      },
      {
        heading: "Reviews and content",
        body: "Reviews must reflect a real booking. We may remove content that is abusive, misleading, or unlawful.",
      },
      {
        heading: "Changes",
        body: "We may update these terms. Continuing to use the app after a change means you accept the updated terms.",
      },
    ],
  },
};

type LegalScreenProps = NativeStackScreenProps<RootStackParamList, "Legal">;

export function LegalScreen({ route }: LegalScreenProps) {
  const document = LEGAL_DOCUMENTS[route.params.document];

  return (
    <ScreenContainer>
      <Text style={styles.title}>{document.title}</Text>

      <View style={styles.notice}>
        <Text style={styles.noticeTitle}>Demo only</Text>
        <Text style={styles.noticeBody}>
          This is placeholder text, not a legal agreement. The final wording is
          coming soon.
        </Text>
      </View>

      {document.sections.map((section) => (
        <View key={section.heading} style={styles.section}>
          <Text style={styles.heading}>{section.heading}</Text>
          <Text style={styles.body}>{section.body}</Text>
        </View>
      ))}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "700",
  },
  notice: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  noticeTitle: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  noticeBody: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 21,
  },
  section: {
    gap: spacing.xs,
  },
  heading: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "700",
  },
  body: {
    color: colors.mutedText,
    fontSize: 15,
    lineHeight: 23,
  },
});
