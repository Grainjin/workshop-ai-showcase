import { ReactNode } from "react";
import { ScrollView, StyleSheet, ViewStyle } from "react-native";

import { useIsWebDesktop } from "../layout/useIsWebDesktop";
import { colors, layout, spacing } from "../theme/theme";

type ScreenContainerProps = {
  children: ReactNode;
  contentStyle?: ViewStyle;
};

export function ScreenContainer({ children, contentStyle }: ScreenContainerProps) {
  const isWebDesktop = useIsWebDesktop();

  return (
    <ScrollView
      contentContainerStyle={[
        styles.content,
        isWebDesktop ? styles.contentDesktop : null,
        contentStyle,
      ]}
      style={[styles.container, isWebDesktop ? styles.containerDesktop : null]}
    >
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  containerDesktop: {
    backgroundColor: colors.surface,
  },
  content: {
    flexGrow: 1,
    gap: spacing.md,
    padding: spacing.lg,
  },
  contentDesktop: {
    width: "100%",
    maxWidth: layout.webContentMaxWidth,
    alignSelf: "center",
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xl,
  },
});
