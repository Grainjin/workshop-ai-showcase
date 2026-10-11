import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { Plus } from "lucide-react-native";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getProviderPortfolios } from "../../api/provider";
import { PortfolioCard } from "../../components/PortfolioCard";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors, spacing } from "../../theme/theme";
import type { PaginatedData } from "../../types/chat";
import type { ProviderPortfolio } from "../../types/provider";

const PAGE_SIZE = 12;

export function ProviderPortfolioListScreen() {
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [items, setItems] = useState<ProviderPortfolio[]>([]);
  const [paging, setPaging] = useState<PaginatedData<ProviderPortfolio> | null>(
    null,
  );
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let isActive = true;

      async function loadFirstPage() {
        setIsLoading(true);
        try {
          const data = await getProviderPortfolios(1, PAGE_SIZE);

          if (isActive) {
            setItems(data?.items ?? []);
            setPaging(data);
            setPage(1);
          }
        } finally {
          if (isActive) {
            setIsLoading(false);
          }
        }
      }

      void loadFirstPage();

      return () => {
        isActive = false;
      };
    }, []),
  );

  async function loadMore() {
    if (isLoadingMore || !paging?.has_next) {
      return;
    }

    setIsLoadingMore(true);
    try {
      const nextPage = page + 1;
      const data = await getProviderPortfolios(nextPage, PAGE_SIZE);

      if (data) {
        setItems((current) => [...current, ...data.items]);
        setPaging(data);
        setPage(nextPage);
      }
    } finally {
      setIsLoadingMore(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.topRow}>
        <Text style={styles.title}>Portfolios</Text>
        <Pressable
          accessibilityRole="button"
          onPress={() => navigation.navigate("ProviderPortfolioCreate")}
          style={styles.addButton}
        >
          <Plus color="#FFFFFF" size={20} />
          <Text style={styles.addText}>Add</Text>
        </Pressable>
      </View>

      {isLoading ? (
        <ActivityIndicator color={colors.primary} style={styles.loader} />
      ) : (
        <FlatList
          ListEmptyComponent={<Text style={styles.emptyText}>No portfolios uploaded yet</Text>}
          ListFooterComponent={
            isLoadingMore ? (
              <ActivityIndicator color={colors.primary} style={styles.footerLoader} />
            ) : null
          }
          columnWrapperStyle={styles.gridRow}
          contentContainerStyle={styles.listContent}
          data={items}
          keyExtractor={(item) => String(item.id)}
          numColumns={2}
          onEndReached={() => void loadMore()}
          onEndReachedThreshold={0.4}
          renderItem={({ item }) => (
            <PortfolioCard
              onPress={() =>
                navigation.navigate("ProviderPortfolioDetail", {
                  portfolioId: item.id,
                })
              }
              portfolio={item}
            />
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing.lg,
    paddingBottom: spacing.sm,
  },
  title: {
    color: colors.text,
    fontSize: 24,
    fontWeight: "800",
  },
  addButton: {
    minHeight: 40,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderRadius: 20,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
  },
  addText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "800",
  },
  loader: {
    marginTop: spacing.xl,
  },
  listContent: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  gridRow: {
    justifyContent: "space-between",
    gap: spacing.md,
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 15,
  },
  footerLoader: {
    paddingVertical: spacing.lg,
  },
});
