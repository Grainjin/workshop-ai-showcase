import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import {
  Bot,
  Check,
  ChevronRight,
  RefreshCw,
  SendHorizontal,
  X,
} from "lucide-react-native";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { ReactNode } from "react";

import {
  cancelAIAction,
  clearAIChatMessages,
  confirmAIAction,
  getAIChatMessages,
  sendAIChatMessage,
} from "../../api/ai";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors, radius, spacing } from "../../theme/theme";
import type {
  AIChatHistoryMessage,
  AIChatResponse,
  AIConfirmationCard,
  AIBookingDraft,
  AIProviderRecommendation,
} from "../../types/ai";
import { getErrorMessage } from "../../utils/errors";

type AIChatMessageItem = {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  response?: AIChatResponse | null;
};

const WELCOME_MESSAGE = "How can I help you today?";

export function CustomerAIChatScreen() {
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const listRef = useRef<FlatList<AIChatMessageItem>>(null);
  const [messages, setMessages] = useState<AIChatMessageItem[]>([]);
  const [inputText, setInputText] = useState("");
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const candidateProviderIds = useMemo(
    () => getLatestCandidateProviderIds(messages),
    [messages],
  );
  const invertedMessages = useMemo(() => [...messages].reverse(), [messages]);

  const scrollToBottom = useCallback((animated = true) => {
    requestAnimationFrame(() => {
      listRef.current?.scrollToOffset({ animated, offset: 0 });
    });
    setTimeout(() => {
      listRef.current?.scrollToOffset({ animated, offset: 0 });
    }, 80);
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadHistory() {
      setIsLoadingHistory(true);

      try {
        const data = await getAIChatMessages(1, 50);
        if (!isMounted) {
          return;
        }

        const historyMessages =
          data?.items.map(formatHistoryMessageForUI) ?? [];
        setMessages(
          historyMessages.length > 0
            ? historyMessages
            : [createAssistantMessage(WELCOME_MESSAGE)],
        );
      } catch {
        if (isMounted) {
          setMessages([createAssistantMessage(WELCOME_MESSAGE)]);
        }
      } finally {
        if (isMounted) {
          setIsLoadingHistory(false);
        }
      }
    }

    void loadHistory();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (messages.length > 0) {
      scrollToBottom();
    }
  }, [messages.length, scrollToBottom]);

  async function handleSend() {
    const cleanText = inputText.trim();

    if (!cleanText || isSending) {
      return;
    }

    setMessages((currentMessages) => [
      ...currentMessages,
      createUserMessage(cleanText),
    ]);
    setInputText("");

    setIsSending(true);
    try {
      const response = await sendAIChatMessage({
        message: cleanText,
        candidate_provider_ids: candidateProviderIds,
      });

      setMessages((currentMessages) => [
        ...currentMessages,
        createAssistantMessage(
          response?.answer || "I couldn't complete that request.",
          response,
        ),
      ]);
    } catch (error) {
      setMessages((currentMessages) => [
        ...currentMessages,
        createAssistantMessage(`AI reply failed: ${getErrorMessage(error)}`),
      ]);
    } finally {
      setIsSending(false);
    }
  }

  async function handleConfirmAction(card: AIConfirmationCard) {
    if (actionLoadingId) {
      return;
    }

    setActionLoadingId(card.action_id);
    try {
      const result = await confirmAIAction(card.action_id);
      const paymentPageUrl =
        typeof result?.result?.payment_page_url === "string"
          ? result.result.payment_page_url
          : null;
      if (paymentPageUrl) {
        await Linking.openURL(paymentPageUrl);
      }
      setMessages((currentMessages) => [
        ...removeConfirmationCard(currentMessages, card.action_id),
        createAssistantMessage(
          result?.executed ? "Action completed." : "Action submitted.",
        ),
      ]);
    } catch (error) {
      Alert.alert("Couldn't complete action", getErrorMessage(error));
    } finally {
      setActionLoadingId(null);
    }
  }

  async function handleCancelAction(card: AIConfirmationCard) {
    if (actionLoadingId) {
      return;
    }

    setActionLoadingId(card.action_id);
    try {
      await cancelAIAction(card.action_id);
      setMessages((currentMessages) => [
        ...removeConfirmationCard(currentMessages, card.action_id),
        createAssistantMessage("This action was cancelled."),
      ]);
    } catch (error) {
      Alert.alert("Couldn't cancel", getErrorMessage(error));
    } finally {
      setActionLoadingId(null);
    }
  }

  function handleClearChatPress() {
    if (isClearing) {
      return;
    }

    if (Platform.OS === "web" && typeof window !== "undefined") {
      if (window.confirm("Clear all AI chat messages?")) {
        void handleClearChat();
      }
      return;
    }

    Alert.alert("Clear history", "Clear all AI chat messages?", [
      {
        text: "Cancel",
        style: "cancel",
      },
      {
        text: "Clear",
        style: "destructive",
        onPress: () => void handleClearChat(),
      },
    ]);
  }

  async function handleClearChat() {
    setIsClearing(true);
    try {
      await clearAIChatMessages();
      setMessages([createAssistantMessage(WELCOME_MESSAGE)]);
      setInputText("");
    } catch (error) {
      Alert.alert("Couldn't clear history", getErrorMessage(error));
    } finally {
      setIsClearing(false);
    }
  }

  function handleOpenProvider(provider: AIProviderRecommendation) {
    navigation.navigate("CustomerProviderDetail", {
      providerId: provider.provider_id,
      providerTag: getProviderTags(provider)[0],
    });
  }

  if (isLoadingHistory) {
    return (
      <View style={styles.centerBox}>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.centerText}>Opening AI assistant...</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={88}
      style={styles.container}
    >
      <Pressable
        accessibilityLabel="Clear chat history"
        accessibilityRole="button"
        disabled={isClearing}
        onPress={handleClearChatPress}
        style={[styles.clearButton, isClearing ? styles.clearButtonDisabled : null]}
      >
        {isClearing ? (
          <ActivityIndicator color={colors.primary} size="small" />
        ) : (
          <RefreshCw color={colors.primary} size={19} />
        )}
      </Pressable>

      <FlatList
        contentContainerStyle={styles.messageList}
        data={invertedMessages}
        inverted
        keyExtractor={(item) => item.id}
        ref={listRef}
        renderItem={({ item }) => (
          <AIMessageBubble
            actionLoadingId={actionLoadingId}
            message={item}
            onCancelAction={handleCancelAction}
            onConfirmAction={handleConfirmAction}
            onOpenProvider={handleOpenProvider}
          />
        )}
      />

      {isSending ? (
        <View style={styles.typingRow}>
          <ActivityIndicator color={colors.primary} size="small" />
          <Text style={styles.typingText}>AI is thinking...</Text>
        </View>
      ) : null}

      <View style={styles.inputBar}>
        <TextInput
          multiline
          onChangeText={setInputText}
          onSubmitEditing={() => {
            if (Platform.OS === "web") {
              void handleSend();
            }
          }}
          placeholder="Find providers, check reviews, or manage bookings"
          placeholderTextColor={colors.mutedText}
          style={styles.input}
          value={inputText}
        />
        <Pressable
          accessibilityRole="button"
          disabled={!inputText.trim() || isSending}
          onPress={() => void handleSend()}
          style={[
            styles.sendButton,
            !inputText.trim() || isSending ? styles.sendButtonDisabled : null,
          ]}
        >
          <SendHorizontal
            color={!inputText.trim() || isSending ? colors.mutedText : "#FFFFFF"}
            size={21}
          />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

function AIMessageBubble({
  message,
  actionLoadingId,
  onOpenProvider,
  onConfirmAction,
  onCancelAction,
}: {
  message: AIChatMessageItem;
  actionLoadingId: number | null;
  onOpenProvider: (provider: AIProviderRecommendation) => void;
  onConfirmAction: (card: AIConfirmationCard) => void;
  onCancelAction: (card: AIConfirmationCard) => void;
}) {
  const isUser = message.role === "user";
  const recommendations = message.response?.recommendations ?? [];
  const confirmationCard = message.response?.confirmation_card ?? null;
  const bookingDraft = message.response?.booking_draft ?? null;

  return (
    <View style={[styles.messageBlock, isUser ? styles.messageBlockUser : null]}>
      {!isUser ? (
        <View style={styles.botAvatar}>
          <Bot color={colors.primary} size={18} />
        </View>
      ) : null}

      <View style={[styles.bubble, isUser ? styles.userBubble : styles.aiBubble]}>
        {isUser ? (
          <Text style={[styles.messageText, styles.userMessageText]}>
            {message.text}
          </Text>
        ) : (
          <AIMessageMarkdown text={message.text} />
        )}

        {!isUser && recommendations.length > 0 ? (
          <View style={styles.recommendationList}>
            {recommendations.map((provider) => (
              <Pressable
                accessibilityRole="button"
                key={provider.provider_id}
                onPress={() => onOpenProvider(provider)}
                style={styles.providerCard}
              >
                <Text style={styles.providerName} numberOfLines={1}>
                  {provider.business_name}
                </Text>
                <Text style={styles.providerMeta} numberOfLines={1}>
                  {getProviderTags(provider).join(" · ") || "No tags"}
                </Text>
                <Text style={styles.providerMeta} numberOfLines={1}>
                  {provider.service_province || "Unknown area"} ·{" "}
                  {provider.hourly_rate ?? "-"} / hr
                </Text>
                <Text style={styles.providerReason} numberOfLines={2}>
                  {provider.reason || "View profile"}
                </Text>
                <View style={styles.providerOpenRow}>
                  <Text style={styles.providerOpenText}>View provider profile</Text>
                  <ChevronRight color={colors.primary} size={16} />
                </View>
              </Pressable>
            ))}
          </View>
        ) : null}

        {!isUser && bookingDraft?.preview ? (
          <View style={styles.infoCard}>
            <Text style={styles.infoCardTitle}>Booking draft</Text>
            <Text style={styles.infoCardText}>
              {bookingDraft.next_question ||
                `Missing: ${bookingDraft.missing_field_names?.join(", ") || "required details"}`}
            </Text>
          </View>
        ) : null}

        {!isUser && confirmationCard?.status === "pending" ? (
          <ConfirmationCard
            card={confirmationCard}
            isLoading={actionLoadingId === confirmationCard.action_id}
            onCancel={() => onCancelAction(confirmationCard)}
            onConfirm={() => onConfirmAction(confirmationCard)}
          />
        ) : null}
      </View>
    </View>
  );
}

function AIMessageMarkdown({ text }: { text: string }) {
  const blocks = parseMarkdownBlocks(text);

  return (
    <View style={styles.markdownContainer}>
      {blocks.map((block, index) => {
        if (block.type === "table") {
          return (
            <MarkdownTable
              key={`table-${index}`}
              header={block.header}
              rows={block.rows}
            />
          );
        }

        return (
          <View key={`text-${index}`} style={styles.markdownTextBlock}>
            {block.lines.map((line, lineIndex) =>
              line.trim() ? (
                <Text
                  key={`${index}-${lineIndex}`}
                  style={styles.messageText}
                >
                  {renderInlineMarkdown(line, `${index}-${lineIndex}`)}
                </Text>
              ) : (
                <View
                  key={`${index}-${lineIndex}`}
                  style={styles.markdownEmptyLine}
                />
              ),
            )}
          </View>
        );
      })}
    </View>
  );
}

type MarkdownTextBlock = {
  type: "text";
  lines: string[];
};

type MarkdownTableBlock = {
  type: "table";
  header: string[];
  rows: string[][];
};

type MarkdownBlock = MarkdownTextBlock | MarkdownTableBlock;

function parseMarkdownBlocks(text: string): MarkdownBlock[] {
  const lines = text.split(/\r?\n/);
  const blocks: MarkdownBlock[] = [];
  let textLines: string[] = [];
  let index = 0;

  function flushTextLines() {
    if (textLines.length > 0) {
      blocks.push({
        type: "text",
        lines: textLines,
      });
      textLines = [];
    }
  }

  while (index < lines.length) {
    const currentLine = lines[index];
    const nextLine = lines[index + 1];

    if (isMarkdownTableHeader(currentLine, nextLine)) {
      flushTextLines();

      const tableLines = [currentLine];
      index += 2;

      while (index < lines.length && isMarkdownTableRow(lines[index])) {
        tableLines.push(lines[index]);
        index += 1;
      }

      const [headerLine, ...rowLines] = tableLines;
      blocks.push({
        type: "table",
        header: parseMarkdownTableRow(headerLine),
        rows: rowLines.map(parseMarkdownTableRow),
      });
      continue;
    }

    textLines.push(currentLine);
    index += 1;
  }

  flushTextLines();

  return blocks;
}

function isMarkdownTableHeader(line?: string, separatorLine?: string) {
  return Boolean(
    line &&
      separatorLine &&
      isMarkdownTableRow(line) &&
      /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(
        separatorLine,
      ),
  );
}

function isMarkdownTableRow(line?: string) {
  return Boolean(line && line.trim().startsWith("|") && line.includes("|"));
}

function parseMarkdownTableRow(line: string) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => stripMarkdown(cell.trim()));
}

function stripMarkdown(value: string) {
  return value.replace(/\*\*(.*?)\*\*/g, "$1").trim();
}

function renderInlineMarkdown(text: string, keyPrefix: string): ReactNode[] {
  return text.split(/(\*\*.*?\*\*)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <Text key={`${keyPrefix}-bold-${index}`} style={styles.markdownBold}>
          {part.slice(2, -2)}
        </Text>
      );
    }

    return <Text key={`${keyPrefix}-text-${index}`}>{part}</Text>;
  });
}

function MarkdownTable({
  header,
  rows,
}: {
  header: string[];
  rows: string[][];
}) {
  return (
    <View style={styles.markdownTable}>
      <View style={[styles.markdownTableRow, styles.markdownTableHeaderRow]}>
        {header.map((cell, index) => (
          <Text
            key={`header-${cell}-${index}`}
            style={[styles.markdownTableCell, styles.markdownTableHeaderCell]}
          >
            {cell}
          </Text>
        ))}
      </View>
      {rows.map((row, rowIndex) => (
        <View key={`row-${rowIndex}`} style={styles.markdownTableRow}>
          {header.map((_, cellIndex) => (
            <Text
              key={`cell-${rowIndex}-${cellIndex}`}
              style={styles.markdownTableCell}
            >
              {row[cellIndex] ?? ""}
            </Text>
          ))}
        </View>
      ))}
    </View>
  );
}

function ConfirmationCard({
  card,
  isLoading,
  onConfirm,
  onCancel,
}: {
  card: AIConfirmationCard;
  isLoading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <View style={styles.confirmationCard}>
      <Text style={styles.confirmationTitle}>{card.title}</Text>
      {card.description ? (
        <Text style={styles.confirmationText}>{card.description}</Text>
      ) : null}
      {card.fields?.map((field, index) => (
        <View key={`${field.label ?? "field"}-${index}`} style={styles.fieldRow}>
          <Text style={styles.fieldLabel}>{field.label ?? "Field"}</Text>
          <Text style={styles.fieldValue}>{formatUnknownValue(field.value)}</Text>
        </View>
      ))}
      {card.warning ? (
        <Text style={styles.warningText}>{card.warning}</Text>
      ) : null}
      <View style={styles.actionRow}>
        <Pressable
          accessibilityRole="button"
          disabled={isLoading}
          onPress={onCancel}
          style={[styles.cardActionButton, styles.cancelButton]}
        >
          <X color={colors.text} size={16} />
          <Text style={styles.cancelButtonText}>
            {card.cancel_label || "Cancel"}
          </Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={isLoading}
          onPress={onConfirm}
          style={[styles.cardActionButton, styles.confirmButton]}
        >
          {isLoading ? (
            <ActivityIndicator color="#FFFFFF" size="small" />
          ) : (
            <>
              <Check color="#FFFFFF" size={16} />
              <Text style={styles.confirmButtonText}>
                {card.confirm_label || "Confirm"}
              </Text>
            </>
          )}
        </Pressable>
      </View>
    </View>
  );
}

function createUserMessage(text: string): AIChatMessageItem {
  return {
    id: `local-user-${Date.now()}-${Math.random()}`,
    role: "user",
    text,
    createdAt: new Date().toISOString(),
  };
}

function createAssistantMessage(
  text: string,
  response: AIChatResponse | null = null,
): AIChatMessageItem {
  return {
    id: `local-assistant-${Date.now()}-${Math.random()}`,
    role: "assistant",
    text,
    createdAt: new Date().toISOString(),
    response,
  };
}

function removeConfirmationCard(
  messages: AIChatMessageItem[],
  actionId: number,
) {
  return messages.map((message) => {
    if (message.response?.confirmation_card?.action_id !== actionId) {
      return message;
    }

    return {
      ...message,
      response: {
        ...message.response,
        confirmation_card: null,
      },
    };
  });
}

function formatHistoryMessageForUI(
  message: AIChatHistoryMessage,
): AIChatMessageItem {
  return {
    id: `history-${message.id}`,
    role: message.role === "user" ? "user" : "assistant",
    text: message.message,
    createdAt: message.created_at,
    response: buildHistoryAIResponse(message),
  };
}

function buildHistoryAIResponse(
  message: AIChatHistoryMessage,
): AIChatResponse | null {
  if (message.role === "user" || !message.response_type) {
    return null;
  }

  const metadata = message.metadata ?? {};
  const recommendations = readRecommendationsFromMetadata(metadata);

  return {
    message: message.message,
    type: message.response_type,
    answer: message.message,
    recommendations,
    recommendation_count:
      readNumber(metadata.recommendation_count) ?? recommendations.length,
    candidate_provider_ids: recommendations.map((provider) => provider.provider_id),
    service_province: readString(metadata.service_province),
    max_price: readNumber(metadata.max_price),
    latitude: readNumber(metadata.latitude),
    longitude: readNumber(metadata.longitude),
    max_distance_km: readNumber(metadata.max_distance_km),
    scheduled_start_time: readString(metadata.scheduled_start_time),
    scheduled_end_time: readString(metadata.scheduled_end_time),
    confirmation_card: readObject(metadata.confirmation_card) as
      | AIConfirmationCard
      | null,
    booking_draft: readObject(metadata.booking_draft) as AIBookingDraft | null,
    next_question: readString(metadata.next_question),
    tool_error: readObject(metadata.tool_error),
  };
}

function readRecommendationsFromMetadata(
  metadata: Record<string, unknown>,
): AIProviderRecommendation[] {
  const source =
    readArray(metadata.recommendations) ??
    readArray(metadata.recommended_providers) ??
    [];

  return source
    .map(normalizeRecommendation)
    .filter((provider): provider is AIProviderRecommendation => provider !== null);
}

function normalizeRecommendation(value: unknown): AIProviderRecommendation | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const data = value as Record<string, unknown>;
  const providerId = readNumber(data.provider_id);

  if (!providerId) {
    return null;
  }

  return {
    provider_id: providerId,
    business_name: readString(data.business_name) || `Provider ${providerId}`,
    service_province: readString(data.service_province),
    tags: readTags(data.tags),
    hourly_rate: readNumber(data.hourly_rate),
    distance_km: readNumber(data.distance_km),
    match_score: readNumber(data.match_score),
    matched_tags: readTags(data.matched_tags),
    reason: readString(data.reason) ?? undefined,
    stats: {
      average_rating:
        readNumber(data.average_rating) ??
        readNumber(readObject(data.stats)?.average_rating),
      review_count:
        readNumber(data.review_count) ?? readNumber(readObject(data.stats)?.review_count),
      completed_bookings:
        readNumber(data.completed_bookings) ??
        readNumber(readObject(data.stats)?.completed_bookings),
    },
  };
}

function readObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  return value as Record<string, unknown>;
}

function readArray(value: unknown): unknown[] | null {
  return Array.isArray(value) ? value : null;
}

function readString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function readNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string" && value.trim()) {
    const parsedValue = Number(value);
    return Number.isFinite(parsedValue) ? parsedValue : null;
  }

  return null;
}

function readTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((tag): tag is string => typeof tag === "string")
      .map((tag) => tag.trim())
      .filter(Boolean);
  }

  if (typeof value === "string") {
    return value
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
  }

  return [];
}

function getLatestCandidateProviderIds(messages: AIChatMessageItem[]) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const recommendations = messages[index].response?.recommendations;
    if (recommendations?.length) {
      return recommendations.map((provider) => provider.provider_id);
    }
  }

  return [];
}

function getProviderTags(provider: AIProviderRecommendation) {
  if (Array.isArray(provider.tags)) {
    return provider.tags;
  }

  return provider.tags
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function formatUnknownValue(value: unknown) {
  if (value == null || value === "") {
    return "-";
  }

  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }

  return JSON.stringify(value);
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  centerBox: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  centerText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  messageList: {
    flexGrow: 1,
    gap: spacing.md,
    padding: spacing.lg,
  },
  clearButton: {
    position: "absolute",
    top: spacing.md,
    right: spacing.lg,
    zIndex: 10,
    width: 38,
    height: 38,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "#BFE8D7",
    borderRadius: 19,
    backgroundColor: "#F2FBF7",
  },
  clearButtonDisabled: {
    opacity: 0.55,
  },
  messageBlock: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
  },
  messageBlockUser: {
    justifyContent: "flex-end",
  },
  botAvatar: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
  },
  bubble: {
    maxWidth: "82%",
    gap: spacing.sm,
    borderRadius: 14,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  aiBubble: {
    backgroundColor: colors.surface,
  },
  userBubble: {
    backgroundColor: colors.primary,
  },
  messageText: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  userMessageText: {
    color: "#FFFFFF",
  },
  markdownContainer: {
    gap: spacing.xs,
  },
  markdownTextBlock: {
    gap: 2,
  },
  markdownEmptyLine: {
    height: spacing.sm,
  },
  markdownBold: {
    fontWeight: "800",
  },
  markdownTable: {
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    backgroundColor: colors.background,
  },
  markdownTableRow: {
    flexDirection: "row",
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  markdownTableHeaderRow: {
    borderTopWidth: 0,
    backgroundColor: "#F4F6F8",
  },
  markdownTableCell: {
    minWidth: 72,
    flex: 1,
    borderLeftWidth: 1,
    borderLeftColor: colors.border,
    color: colors.text,
    fontSize: 12,
    lineHeight: 17,
    paddingHorizontal: spacing.xs,
    paddingVertical: 6,
  },
  markdownTableHeaderCell: {
    color: colors.text,
    fontWeight: "800",
  },
  recommendationList: {
    gap: spacing.sm,
  },
  providerCard: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.sm,
  },
  providerName: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "800",
  },
  providerMeta: {
    color: colors.mutedText,
    fontSize: 12,
  },
  providerReason: {
    color: colors.text,
    fontSize: 12,
    lineHeight: 17,
  },
  providerOpenRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 2,
    paddingTop: spacing.xs,
  },
  providerOpenText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
  },
  infoCard: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.sm,
  },
  infoCardTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800",
  },
  infoCardText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  confirmationCard: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.sm,
  },
  confirmationTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "800",
  },
  confirmationText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  fieldRow: {
    gap: spacing.xs,
  },
  fieldLabel: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: "700",
  },
  fieldValue: {
    color: colors.text,
    fontSize: 13,
    lineHeight: 18,
  },
  warningText: {
    color: colors.danger,
    fontSize: 12,
    lineHeight: 17,
  },
  actionRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  cardActionButton: {
    minHeight: 38,
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
  },
  cancelButton: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  confirmButton: {
    backgroundColor: colors.primary,
  },
  cancelButtonText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "800",
  },
  confirmButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "800",
  },
  typingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  typingText: {
    color: colors.mutedText,
    fontSize: 13,
  },
  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  input: {
    maxHeight: 124,
    minHeight: 46,
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    color: colors.text,
    fontSize: 15,
    lineHeight: 20,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  sendButton: {
    width: 46,
    height: 46,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.primary,
  },
  sendButtonDisabled: {
    backgroundColor: colors.surface,
  },
});
