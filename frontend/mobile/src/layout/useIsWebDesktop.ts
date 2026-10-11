import { Platform, useWindowDimensions } from "react-native";

import { layout } from "../theme/theme";

export function useIsWebDesktop() {
  const { width } = useWindowDimensions();

  return Platform.OS === "web" && width >= layout.webDesktopMinWidth;
}
