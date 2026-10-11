import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import * as ImagePicker from "expo-image-picker";
import { CalendarClock, MapPin, Send, SendHorizontal } from "lucide-react-native";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ActivityIndicator,
  Alert,
  AppState,
  FlatList,
  Linking,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  buildChatWebSocketUrl,
  getBookingById,
  getChatMessages,
  sendChatMessage,
} from "../api/chat";
import { getAccessToken } from "../api/client";
import {
  acceptCustomerBookingQuote,
  acceptCustomerFinalQuote,
  appealCustomerRefund,
  cancelCustomerBooking,
  cancelCustomerBookingAfterVisit,
  cancelCustomerRefund,
  confirmCustomerBookingComplete,
  createCustomerReview,
  createCustomerBooking,
  getCustomerProviderDetail,
  getCustomerPayments,
  payCustomerBooking,
  rejectCustomerBookingQuote,
  rejectCustomerFinalQuote,
  requestCustomerRefund,
  updateCustomerPendingBooking,
} from "../api/customer";
import {
  approveProviderRefundRequest,
  completeProviderBooking,
  quoteProviderBooking,
  startProviderVisit,
  submitProviderFinalQuote,
  rejectProviderRefundRequest,
  rejectProviderBooking,
} from "../api/provider";
import {
  BookingRequestModal,
  buildBookingRequestPayload,
  createDefaultBookingRequestForm,
  type BookingRequestFormState,
} from "../components/BookingRequestModal";
import { CompletionProofGallery } from "../components/CompletionProofGallery";
import { BookingPriceBreakdown } from "../components/BookingPriceBreakdown";
import { BookingCoreDetails } from "../components/BookingCoreDetails";
import { BookingContextInformation } from "../components/BookingContextInformation";
import { CustomerBookingDetailModal } from "../components/CustomerBookingDetailModal";
import { ProviderBookingDetailModal } from "../components/ProviderBookingDetailModal";
import { MarketplaceBreakdownCard } from "../components/MarketplaceBreakdownCard";
import { ActionReasonModal } from "../components/ActionReasonModal";
import { CustomerReviewModal } from "../components/CustomerReviewModal";
import { DateTimeField } from "../components/DateTimeField";
import { PrimaryButton } from "../components/PrimaryButton";
import { SecondaryButton } from "../components/SecondaryButton";
import { TextField } from "../components/TextField";
import { useAuth } from "../context/AuthContext";
import { useRealtime } from "../context/RealtimeContext";
import { DEMO_MODE } from "../config/env";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { colors, radius, spacing } from "../theme/theme";
import type {
  BookingDetail,
  BookingPayload,
  BookingUploadFile,
  PaymentSummary,
} from "../types/booking";
import type { ChatMessage } from "../types/chat";
import type { ProviderProfile } from "../types/provider";
import { getErrorMessage } from "../utils/errors";
import { formatShortDateTime, toEditableDateTime } from "../utils/datetime";
import { formatMoney, formatPayLabel } from "../utils/money";
import { useConfirmation } from "../utils/useConfirmation";
import { resolveBookingReferenceDetail } from "../utils/referencePrice";
import {
  createPaymentIdempotencyKey,
  shouldRotatePaymentIdempotencyKey,
  indexLatestPayments,
} from "../utils/payment";
import {
  canCustomerCancelBooking,
  canCustomerRequestRefund as canCustomerRequestRefundForBooking,
  getCustomerBookingListAction,
  shouldShowBookingInChat,
  shouldShowFinalQuote,
  shouldShowInitialQuote,
  shouldShowInitialQuoteHistory,
  type CustomerBookingListAction,
} from "../utils/bookingActions";
import {
  getBookingStatusLabelForChat,
  getPaymentStatusLabel,
  getRefundStatusLabel,
} from "../constants/labels";

type ChatRoomScreenProps = NativeStackScreenProps<RootStackParamList, "ChatRoom">;

type ChatDisplayItem = {
  key: string;
  message: ChatMessage;
  variant: "message" | "booking" | "booking_update";
};

type ChatReasonAction =
  | "reject_booking"
  | "reject_quote"
  | "reject_final_quote"
  | "refund"
  | "reject_refund";
export function ChatRoomScreen({ navigation, route }: ChatRoomScreenProps) {
  const { user } = useAuth();
  const { markChatRoomRead } = useRealtime();
  const { confirmationModal, requestConfirmation } = useConfirmation();
  const listRef = useRef<FlatList<ChatDisplayItem>>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedBooking, setSelectedBooking] = useState<BookingDetail | null>(null);
  const [selectedBookingPayment, setSelectedBookingPayment] = useState<PaymentSummary | null>(null);
  const [bookingForm, setBookingForm] = useState<BookingRequestFormState | null>(
    null,
  );
  const [quoteAmount, setQuoteAmount] = useState("");
  const [visitFeeAmount, setVisitFeeAmount] = useState("");
  const [quoteAmountError, setQuoteAmountError] = useState("");
  const [visitFeeError, setVisitFeeError] = useState("");
  const [quoteMessage, setQuoteMessage] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [quoteRejectReason, setQuoteRejectReason] = useState("");
  const [refundReason, setRefundReason] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundAppealReason, setRefundAppealReason] = useState("");
  const [refundRejectReason, setRefundRejectReason] = useState("");
  const [reasonAction, setReasonAction] = useState<ChatReasonAction | null>(null);
  const [proofAssets, setProofAssets] = useState<ImagePicker.ImagePickerAsset[]>([]);
  const [quoteFiles, setQuoteFiles] = useState<BookingUploadFile[]>([]);
  const [quoteFilesError, setQuoteFilesError] = useState("");
  const [finalQuoteAmount, setFinalQuoteAmount] = useState("");
  const [finalQuoteMessage, setFinalQuoteMessage] = useState("");
  const [bookingActionError, setBookingActionError] = useState("");
  const [reviewBooking, setReviewBooking] = useState<BookingDetail | null>(null);
  const [reviewError, setReviewError] = useState("");
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [isBookingActionLoading, setIsBookingActionLoading] = useState(false);
  const [isPaymentLoading, setIsPaymentLoading] = useState(false);
  const paymentInFlightRef = useRef(false);
  const paymentIdempotencyKeysRef = useRef<Record<number, string>>({});
  const [isCreateBookingModalVisible, setIsCreateBookingModalVisible] =
    useState(false);
  const [createBookingForm, setCreateBookingForm] =
    useState<BookingRequestFormState>(
      createDefaultBookingRequestForm(),
  );
  const [createBookingError, setCreateBookingError] = useState("");
  const [isCreatingBooking, setIsCreatingBooking] = useState(false);
  const [bookingProvider, setBookingProvider] = useState<ProviderProfile | null>(null);

  function confirmReasonAction() {
    if (!selectedBooking || !reasonAction) {
      return;
    }
    const reason =
      reasonAction === "refund"
        ? refundReason
        : reasonAction === "reject_booking"
          ? rejectReason
          : reasonAction === "reject_refund"
            ? refundRejectReason
            : quoteRejectReason;
    if (!reason.trim()) {
      setBookingActionError("A reason is required for this action.");
      return;
    }
    const action = reasonAction;
    setReasonAction(null);
    if (action === "reject_booking") {
      void handleRejectBooking();
    } else if (action === "reject_quote") {
      void handleRejectQuote();
    } else if (action === "reject_final_quote") {
      void handleRejectFinalQuote();
    } else if (action === "refund") {
      void handleRequestRefund();
    } else {
      void handleRejectRefund();
    }
  }

  const [opponentOnline, setOpponentOnline] = useState(
    Boolean(route.params.opponentOnline),
  );
  const [isAppActive, setIsAppActive] = useState(
    AppState.currentState === "active",
  );

  useEffect(() => {
    markChatRoomRead(route.params.chatRoomId);
  }, [markChatRoomRead, route.params.chatRoomId]);

  const canCreateBooking =
    user?.role === "customer" && Boolean(route.params.providerProfileId);

  useEffect(() => {
    if (!canCreateBooking || !route.params.providerProfileId) {
      setBookingProvider(null);
      return;
    }

    let isActive = true;
    void getCustomerProviderDetail(route.params.providerProfileId)
      .then((detail) => {
        if (isActive) setBookingProvider(detail?.provider ?? null);
      })
      .catch(() => {
        if (isActive) setBookingProvider(null);
      });

    return () => {
      isActive = false;
    };
  }, [canCreateBooking, route.params.providerProfileId]);
  const displayMessages = useMemo(
    () => collapseBookingMessages(messages),
    [messages],
  );
  const bookingCardIds = useMemo(
    () =>
      Array.from(
        new Set(
          displayMessages
            .filter((item) => item.variant === "booking")
            .map((item) => getBookingIdFromMessage(item.message))
            .filter((bookingId): bookingId is number => bookingId != null),
        ),
      ),
    [displayMessages],
  );
  const [bookingPreviews, setBookingPreviews] = useState<Record<number, BookingDetail>>({});
  const [bookingPaymentsById, setBookingPaymentsById] = useState<Record<number, PaymentSummary>>({});
  const pinnedBookingItem = useMemo(
    () => getLatestBookingCardItem(displayMessages, bookingPreviews),
    [bookingPreviews, displayMessages],
  );
  const chatListMessages = useMemo(
    () => displayMessages.filter((item) => item.variant !== "booking"),
    [displayMessages],
  );
  const invertedChatListMessages = useMemo(
    () => [...chatListMessages].reverse(),
    [chatListMessages],
  );

  useEffect(() => {
    let isActive = true;
    const missingBookingIds = bookingCardIds.filter((bookingId) => !bookingPreviews[bookingId]);
    if (missingBookingIds.length === 0) {
      return () => {
        isActive = false;
      };
    }

    void Promise.all(
      missingBookingIds.map(async (bookingId) => {
        try {
          return await getBookingById(bookingId);
        } catch {
          return null;
        }
      }),
    ).then((results) => {
      if (!isActive) return;
      setBookingPreviews((current) => {
        const next = { ...current };
        results.forEach((booking) => {
          if (booking) next[booking.id] = booking;
        });
        return next;
      });
    });

    return () => {
      isActive = false;
    };
  }, [bookingCardIds, bookingPreviews]);

  useEffect(() => {
    if (user?.role !== "customer" || bookingCardIds.length === 0) {
      setBookingPaymentsById({});
      return;
    }

    let isActive = true;
    void getCustomerPayments(1, 100)
      .then((result) => {
        if (isActive) {
          setBookingPaymentsById(indexLatestPayments(result?.items ?? []));
        }
      })
      .catch(() => {
        // The card can fall back to payment metadata from the chat message.
      });

    return () => {
      isActive = false;
    };
  }, [bookingCardIds, user?.role]);

  const scrollToLatestMessage = useCallback((animated = true) => {
    requestAnimationFrame(() => {
      listRef.current?.scrollToOffset({ animated, offset: 0 });
    });
    setTimeout(() => {
      listRef.current?.scrollToOffset({ animated, offset: 0 });
    }, 80);
  }, []);

  useLayoutEffect(() => {
    navigation.setOptions({
      headerTitle: () => (
        <ChatHeaderTitle
          isOnline={opponentOnline}
          title={route.params.title}
        />
      ),
      headerRight: () =>
        canCreateBooking ? (
          <Pressable
            accessibilityLabel="Request booking"
            accessibilityRole="button"
            disabled={isCreatingBooking}
            onPress={() => {
              setCreateBookingForm(createDefaultBookingRequestForm(bookingProvider));
              setCreateBookingError("");
              setIsCreateBookingModalVisible(true);
            }}
            style={styles.headerOrderButton}
          >
            <Send color="#FFFFFF" size={17} />
            <Text style={styles.headerOrderButtonText}>Booking</Text>
          </Pressable>
        ) : null,
    });
  }, [
    canCreateBooking,
    bookingProvider,
    isCreatingBooking,
    navigation,
    opponentOnline,
    route.params.title,
  ]);

  const loadMessages = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage("");

    try {
      const data = await getChatMessages(route.params.chatRoomId);
      setMessages(data?.items ?? []);
    } catch {
      setMessages([]);
      setErrorMessage("Couldn't load chat history.");
    } finally {
      setIsLoading(false);
    }
  }, [route.params.chatRoomId]);

  useEffect(() => {
    void loadMessages();
  }, [loadMessages]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      setIsAppActive(nextState === "active");
    });

    return () => {
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    const token = getAccessToken();

    if (!token || !isAppActive) {
      return;
    }

    const websocket = new WebSocket(
      buildChatWebSocketUrl(route.params.chatRoomId),
    );
    websocketRef.current = websocket;

    websocket.onopen = () => {
      websocket.send(JSON.stringify({ type: "auth", token }));
      websocket.send(JSON.stringify({ type: "mark_read" }));
      pingTimerRef.current = setInterval(() => {
        if (websocket.readyState === WebSocket.OPEN) {
          websocket.send(JSON.stringify({ type: "ping" }));
        }
      }, 25000);
    };

    websocket.onmessage = (event) => {
      const data = parseWebSocketMessage(event.data);
      const chatMessage = data?.chat_message;

      if (data?.type === "chat_message" && isIncomingChatMessage(chatMessage)) {
        setMessages((currentMessages) =>
          appendChatMessageWithoutDuplicate(currentMessages, chatMessage),
        );
        if (
          chatMessage.sender_id !== user?.id &&
          websocket.readyState === WebSocket.OPEN
        ) {
          websocket.send(JSON.stringify({ type: "mark_read" }));
        }
        return;
      }

      if (data?.type === "user_online") {
        setOpponentOnline(true);
        return;
      }

      if (data?.type === "user_offline") {
        setOpponentOnline(false);
        return;
      }

      if (data?.type === "error" && typeof data.message === "string") {
        setErrorMessage(data.message);
      }
    };

    websocket.onerror = () => {
      setErrorMessage("Connection lost. Refresh to see new messages.");
    };

    websocket.onclose = () => {
      if (websocketRef.current === websocket) {
        websocketRef.current = null;
      }
    };

    return () => {
      if (pingTimerRef.current) {
        clearInterval(pingTimerRef.current);
        pingTimerRef.current = null;
      }
      websocket.close();
      if (websocketRef.current === websocket) {
        websocketRef.current = null;
      }
    };
  }, [isAppActive, route.params.chatRoomId, user?.id]);

  useEffect(() => {
    if (chatListMessages.length > 0) {
      scrollToLatestMessage();
    }
  }, [chatListMessages.length, scrollToLatestMessage]);

  async function handleSend() {
    const cleanText = inputText.trim();

    if (!cleanText || isSending) {
      return;
    }

    setIsSending(true);
    setErrorMessage("");

    try {
      if (websocketRef.current?.readyState === WebSocket.OPEN) {
        websocketRef.current.send(
          JSON.stringify({
            type: "chat_message",
            message: cleanText,
            attachment_ids: [],
          }),
        );
        setInputText("");
        return;
      }

      const data = await sendChatMessage(route.params.chatRoomId, cleanText);
      if (data?.chat_message) {
        setMessages((currentMessages) =>
          appendChatMessageWithoutDuplicate(currentMessages, data.chat_message),
        );
      }
      setInputText("");
    } catch {
      setErrorMessage("Couldn't send message.");
    } finally {
      setIsSending(false);
    }
  }

  async function handleBookingPress(message: ChatMessage) {
    const bookingId = getBookingIdFromMessage(message);

    if (!bookingId) {
      return;
    }

    setIsBookingActionLoading(true);
    try {
      const booking = await getBookingById(bookingId);
      if (booking && isBookingVisibleInActiveBookingsForDetail(booking, user?.role)) {
        let payment: PaymentSummary | null = null;
        if (user?.role === "customer") {
          try {
            const paymentResult = await getCustomerPayments(1, 100);
            payment = indexLatestPayments(paymentResult?.items ?? [])[booking.id] ?? null;
          } catch {
            // The booking detail remains usable even if the payment list is unavailable.
          }
        }
        setSelectedBooking(booking);
        setSelectedBookingPayment(payment);
        setBookingForm(createBookingFormFromDetail(booking));
        setQuoteAmount(
          booking.expected_service_amount == null
            ? booking.quote_amount == null
              ? ""
              : String(booking.quote_amount)
            : String(booking.expected_service_amount),
        );
        setVisitFeeAmount(
          booking.visit_fee_amount == null ? "" : String(booking.visit_fee_amount),
        );
        setQuoteAmountError("");
        setVisitFeeError("");
        setQuoteMessage("");
        setRejectReason("");
        setQuoteRejectReason("");
        setRefundReason("");
        setRefundAmount("");
        setRefundAppealReason("");
        setRefundRejectReason("");
        setProofAssets([]);
        setQuoteFiles([]);
        setQuoteFilesError("");
        setFinalQuoteAmount(
          booking.status === "awaiting_final_quote" && booking.final_quote_declined_at
            ? ""
            : booking.final_quote_amount == null
              ? ""
              : String(booking.final_quote_amount),
        );
        setFinalQuoteMessage(
          booking.status === "awaiting_final_quote" && booking.final_quote_declined_at
            ? ""
            : booking.final_quote_message || "",
        );
        setBookingActionError("");
      }
    } catch (error) {
      Alert.alert("Couldn't load booking", getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  function closeBookingActionModal() {
    setSelectedBooking(null);
    setSelectedBookingPayment(null);
    setBookingForm(null);
    setQuoteAmount("");
    setVisitFeeAmount("");
    setQuoteMessage("");
    setRejectReason("");
    setQuoteRejectReason("");
    setRefundReason("");
    setRefundAmount("");
    setRefundAppealReason("");
    setRefundRejectReason("");
    setProofAssets([]);
    setQuoteFiles([]);
    setQuoteFilesError("");
    setFinalQuoteAmount("");
    setFinalQuoteMessage("");
    setBookingActionError("");
    setQuoteAmountError("");
    setVisitFeeError("");
  }

  async function handleUpdateBooking() {
    if (!selectedBooking || !bookingForm) {
      return;
    }

    const payload = buildUpdatePayload(selectedBooking, bookingForm);
    if (!payload) {
      Alert.alert("Incomplete booking", "Enter a title (maximum 30 words), description, address, and schedule.");
      return;
    }

    setIsBookingActionLoading(true);
    try {
      await updateCustomerPendingBooking(selectedBooking.id, payload);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      Alert.alert("Update failed", getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleQuoteBooking() {
    if (!selectedBooking) {
      return;
    }

    const amount = Number(quoteAmount);
    const visitFee = Number(visitFeeAmount);
    setQuoteAmountError("");
    setVisitFeeError("");
    if (!Number.isFinite(amount) || amount <= 0) {
      setQuoteAmountError("Enter an expected service amount greater than 0.");
      return;
    }
    if (!Number.isFinite(visitFee) || visitFee <= 0) {
      setVisitFeeError("Enter a visit fee greater than 0.");
      return;
    }
    if (visitFee > amount) {
      setVisitFeeError("Visit fee cannot exceed the expected service amount.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await quoteProviderBooking(
        selectedBooking.id,
        amount,
        quoteMessage.trim() || null,
        visitFee,
        quoteFiles,
      );
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      if (errorMessage.toLowerCase().includes("visit fee cannot exceed")) {
        setVisitFeeError(errorMessage);
      } else if (/file|attachment/i.test(errorMessage)) {
        setQuoteFilesError(errorMessage);
      } else {
        setBookingActionError(errorMessage);
      }
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleRejectBooking() {
    if (!selectedBooking) {
      return;
    }

    const reason = rejectReason.trim();
    if (!reason) {
      setBookingActionError("Enter a reason for declining this booking.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await rejectProviderBooking(selectedBooking.id, reason);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleAcceptQuote() {
    if (!selectedBooking) {
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      const result = await acceptCustomerBookingQuote(selectedBooking.id);
      const chatMessage = result?.chat_message;
      setSelectedBooking(
        await resolveBookingReferenceDetail(
          result?.booking ?? selectedBooking,
          getBookingById,
        ),
      );
      if (chatMessage) {
        setMessages((currentMessages) => [...currentMessages, chatMessage]);
      } else {
        await loadMessages();
      }
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleRejectQuote() {
    if (!selectedBooking) {
      return;
    }

    const reason = quoteRejectReason.trim();
    if (!reason) {
      setBookingActionError("Enter a reason for declining the quote.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await rejectCustomerBookingQuote(selectedBooking.id, reason);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleAcceptFinalQuote() {
    if (!selectedBooking) {
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      const result = await acceptCustomerFinalQuote(selectedBooking.id);
      setSelectedBooking(
        await resolveBookingReferenceDetail(
          result?.booking ?? selectedBooking,
          getBookingById,
        ),
      );
      await loadMessages();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      if (errorMessage.toLowerCase().includes("visit fee cannot exceed")) {
        setVisitFeeError(errorMessage);
      } else {
        setBookingActionError(errorMessage);
      }
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleChatPrimaryAction(
    bookingId: number,
    action: CustomerBookingListAction,
    paymentStage: "visit_fee" | "service_fee" = "visit_fee",
  ) {
    if (action === "pay") {
      void handlePayBooking(bookingId, paymentStage);
      return;
    }
    if (isBookingActionLoading) {
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      if (action === "accept_quote") {
        await acceptCustomerBookingQuote(bookingId);
        await loadMessages();
        return;
      }
      if (action === "accept_final_quote") {
        await acceptCustomerFinalQuote(bookingId);
        await loadMessages();
        return;
      }

      const result = await confirmCustomerBookingComplete(bookingId);
      if (result?.payment_page_url) {
        await Linking.openURL(result.payment_page_url);
        setBookingActionError(
          "The final quote changed. Complete the new authorization, then confirm again.",
        );
        await loadMessages();
        return;
      }

      await loadMessages();
      if (result?.booking) {
        setReviewError("");
        setReviewBooking(result.booking);
      }
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleRejectFinalQuote() {
    if (!selectedBooking) {
      return;
    }

    const reason = quoteRejectReason.trim();
    if (!reason) {
      setBookingActionError("Enter a reason for declining the final quote.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await rejectCustomerFinalQuote(selectedBooking.id, reason);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      if (errorMessage.toLowerCase().includes("visit fee cannot exceed")) {
        setVisitFeeError(errorMessage);
      } else {
        setBookingActionError(errorMessage);
      }
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleCancelBooking() {
    if (!selectedBooking) {
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await cancelCustomerBooking(selectedBooking.id);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handlePayBooking(
    bookingId?: number,
    paymentStageOverride?: "visit_fee" | "service_fee",
  ) {
    const targetBookingId = bookingId ?? selectedBooking?.id;
    if (!targetBookingId || paymentInFlightRef.current) {
      return;
    }

    paymentInFlightRef.current = true;
    setIsPaymentLoading(true);
    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      const idempotencyKey =
        paymentIdempotencyKeysRef.current[targetBookingId] ??
        (paymentIdempotencyKeysRef.current[targetBookingId] =
          createPaymentIdempotencyKey());
      const paymentStage =
        paymentStageOverride ??
        (selectedBooking?.status === "awaiting_service_payment"
          ? "service_fee"
          : "visit_fee");
      const result = await payCustomerBooking(
        targetBookingId,
        "iyzico_checkout",
        idempotencyKey,
        paymentStage,
      );

      if (shouldRotatePaymentIdempotencyKey(result?.payment)) {
        delete paymentIdempotencyKeysRef.current[targetBookingId];
      }

      if (result?.payment_page_url) {
        delete paymentIdempotencyKeysRef.current[targetBookingId];
        await Linking.openURL(result.payment_page_url);
      }

      if (bookingId || !selectedBooking) {
        setSelectedBooking(null);
      }
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      paymentInFlightRef.current = false;
      setIsPaymentLoading(false);
      setIsBookingActionLoading(false);
    }
  }

  async function handleCancelAfterVisit() {
    if (!selectedBooking) {
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await cancelCustomerBookingAfterVisit(selectedBooking.id);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  function confirmCancelBooking() {
    if (!selectedBooking) return;
    requestConfirmation({
      title: "Cancel booking?",
      message: "This booking will be cancelled and this action cannot be undone. Any paid amount will not be refunded automatically. If you need a refund, use the refund process separately.",
      onConfirm: () => void handleCancelBooking(),
      confirmLabel: "Cancel",
    });
  }

  function confirmCancelAfterVisit() {
    if (!selectedBooking) return;
    requestConfirmation({
      title: "Cancel booking?",
      message: "The booking will be closed without requesting a refund. Any paid amount will not be refunded automatically. If you need a refund, use the refund process separately.",
      onConfirm: () => void handleCancelAfterVisit(),
      confirmLabel: "Cancel",
    });
  }

  async function handleRequestRefund() {
    if (!selectedBooking) {
      return;
    }

    const reason = refundReason.trim();
    if (!reason) {
      setBookingActionError("Enter a refund reason.");
      return;
    }

    const parsedAmount = refundAmount.trim() ? Number(refundAmount) : undefined;
    if (
      parsedAmount !== undefined &&
      (!Number.isFinite(parsedAmount) ||
        parsedAmount <= 0 ||
        (selectedBooking.quote_amount != null &&
          parsedAmount > selectedBooking.quote_amount))
    ) {
      setBookingActionError("Refund amount must be greater than 0 and no more than the paid amount.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await requestCustomerRefund(
        selectedBooking.id,
        reason,
        parsedAmount,
      );
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleCancelRefund() {
    const refundRequestId = selectedBooking?.current_refund_request?.id;
    if (!refundRequestId) {
      setBookingActionError("This refund request cannot be cancelled.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await cancelCustomerRefund(refundRequestId);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  function confirmCancelRefund() {
    if (!selectedBooking) return;
    requestConfirmation({
      title: "Cancel refund request?",
      message: "The refund request will be withdrawn. You can submit a new request later if the booking remains eligible.",
      onConfirm: () => void handleCancelRefund(),
      confirmLabel: "Cancel refund",
    });
  }

  async function handleAppealRefund() {
    const refundRequestId = selectedBooking?.current_refund_request?.id;
    const reason = refundAppealReason.trim();

    if (!refundRequestId) {
      setBookingActionError("This refund cannot be appealed.");
      return;
    }
    if (!reason) {
      setBookingActionError("Enter an appeal reason.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await appealCustomerRefund(refundRequestId, reason);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleConfirmComplete() {
    if (!selectedBooking) {
      return;
    }

    const bookingToReview = selectedBooking;
    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      const result = await confirmCustomerBookingComplete(bookingToReview.id);
      if (result?.payment_page_url) {
        setSelectedBooking(result.booking ?? bookingToReview);
        await Linking.openURL(result.payment_page_url);
        setBookingActionError(
          "The final quote changed. Complete the new authorization, then confirm again.",
        );
        await loadMessages();
        return;
      }
      setSelectedBooking(null);
      await loadMessages();
      setReviewError("");
      setReviewBooking(
        result?.booking ?? {
          ...bookingToReview,
          status: "completed",
        },
      );
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleSubmitReview(rating: number, comment: string) {
    if (!reviewBooking) {
      return;
    }

    setIsSubmittingReview(true);
    setReviewError("");
    try {
      await createCustomerReview(reviewBooking.id, rating, comment);
      setReviewBooking(null);
      Alert.alert("Review submitted", "Thank you for your feedback.");
    } catch (error) {
      setReviewError(getErrorMessage(error));
    } finally {
      setIsSubmittingReview(false);
    }
  }

  async function handlePickCompletionProof() {
    setBookingActionError("");

    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setBookingActionError("Allow access to photos to attach completion proof.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      allowsMultipleSelection: true,
      mediaTypes: ["images", "videos"],
      quality: 0.85,
      videoQuality: ImagePicker.UIImagePickerControllerQualityType.Medium,
    });

    if (result.canceled || result.assets.length === 0) {
      return;
    }

    setProofAssets(result.assets);
  }

  async function handleStartVisit() {
    if (!selectedBooking || (!DEMO_MODE && proofAssets.length === 0)) {
      setBookingActionError("Add at least one photo or video as arrival evidence.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await startProviderVisit(
        selectedBooking.id,
        DEMO_MODE ? [] : proofAssets.map((asset) => ({
          uri: asset.uri,
          fileName: asset.fileName,
          mimeType: asset.mimeType,
        })),
      );
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      if (errorMessage.toLowerCase().includes("visit fee cannot exceed")) {
        setVisitFeeError(errorMessage);
      } else {
        setBookingActionError(errorMessage);
      }
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleSubmitFinalQuote() {
    if (!selectedBooking) {
      return;
    }

    const amount = Number(finalQuoteAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setBookingActionError("Enter a final quote amount greater than 0.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await submitProviderFinalQuote(
        selectedBooking.id,
        amount,
        finalQuoteMessage.trim() || null,
        quoteFiles,
      );
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      if (errorMessage.toLowerCase().includes("visit fee cannot exceed")) {
        setVisitFeeError(errorMessage);
      } else if (/file|attachment/i.test(errorMessage)) {
        setQuoteFilesError(errorMessage);
      } else {
        setBookingActionError(errorMessage);
      }
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleCompleteBooking() {
    if (!selectedBooking) {
      return;
    }
    if (!DEMO_MODE && proofAssets.length === 0) {
      setBookingActionError("Add at least one photo or video as completion proof.");
      return;
    }
    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await completeProviderBooking(
        selectedBooking.id,
        DEMO_MODE ? [] : proofAssets.map((asset) => ({
          uri: asset.uri,
          fileName: asset.fileName,
          mimeType: asset.mimeType,
        })),
        null,
        null,
      );
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleApproveRefund() {
    const refundRequestId = selectedBooking?.current_refund_request?.id;
    if (!refundRequestId) {
      setBookingActionError("No refund request to review.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await approveProviderRefundRequest(refundRequestId);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleRejectRefund() {
    const refundRequestId = selectedBooking?.current_refund_request?.id;
    const reason = refundRejectReason.trim();

    if (!refundRequestId) {
      setBookingActionError("No refund request to review.");
      return;
    }
    if (!reason) {
      setBookingActionError("Enter a reason for declining the refund.");
      return;
    }

    setIsBookingActionLoading(true);
    setBookingActionError("");
    try {
      await rejectProviderRefundRequest(refundRequestId, reason);
      setSelectedBooking(null);
      await loadMessages();
    } catch (error) {
      setBookingActionError(getErrorMessage(error));
    } finally {
      setIsBookingActionLoading(false);
    }
  }

  async function handleCreateBookingFromChat() {
    if (!route.params.providerProfileId) {
      setCreateBookingError("Provider details are missing. Open this chat from the chat list.");
      return;
    }

    const payload = buildBookingRequestPayload({
      provider: bookingProvider,
      providerProfileId: route.params.providerProfileId,
      chatRoomId: route.params.chatRoomId,
      form: createBookingForm,
    });
    if (!payload) {
      setCreateBookingError("Select a service and enter a title (maximum 30 words), description, address, and schedule.");
      return;
    }

    setIsCreatingBooking(true);
    setCreateBookingError("");
    try {
      const result = await createCustomerBooking(payload);
      if (result?.chat_message) {
        setMessages((currentMessages) =>
          appendChatMessageWithoutDuplicate(currentMessages, result.chat_message),
        );
      } else {
        await loadMessages();
      }
      setIsCreateBookingModalVisible(false);
    } catch (error) {
      setCreateBookingError(getErrorMessage(error));
    } finally {
      setIsCreatingBooking(false);
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={88}
      style={styles.container}
    >
      {isLoading ? (
        <View style={styles.centerBox}>
          <ActivityIndicator color={colors.primary} />
          <Text style={styles.centerText}>Loading chat...</Text>
        </View>
      ) : (
        <View style={styles.chatArea}>
          {pinnedBookingItem ? (
            <View style={styles.pinnedBookingLayer}>
              <MessageBubble
                displayVariant={pinnedBookingItem.variant}
                isMine={pinnedBookingItem.message.sender_id === user?.id}
                isPinned
                message={pinnedBookingItem.message}
                bookingPreview={bookingPreviews[getBookingIdFromMessage(pinnedBookingItem.message) ?? -1]}
                bookingPayment={bookingPaymentsById[getBookingIdFromMessage(pinnedBookingItem.message) ?? -1]}
                onBookingPress={() =>
                  void handleBookingPress(pinnedBookingItem.message)
                }
                onPrimaryAction={(action) => {
                  const bookingId = getBookingIdFromMessage(
                    pinnedBookingItem.message,
                  );
                  if (bookingId) {
                    void handleChatPrimaryAction(
                      bookingId,
                      action,
                      getPaymentStageFromBooking(
                        bookingPreviews[bookingId],
                        pinnedBookingItem.message,
                      ),
                    );
                  }
                }}
                isActionLoading={isBookingActionLoading}
                userRole={user?.role}
              />
            </View>
          ) : null}
          <FlatList
            contentContainerStyle={[
              styles.messageList,
              pinnedBookingItem ? styles.messageListWithPinnedBooking : null,
            ]}
            data={invertedChatListMessages}
            inverted
            keyExtractor={(item) => item.key}
            keyboardShouldPersistTaps="handled"
            ListEmptyComponent={
              <View style={styles.emptyBox}>
                <Text style={styles.emptyText}>No messages yet</Text>
              </View>
            }
            onContentSizeChange={() => scrollToLatestMessage(false)}
            onLayout={() => scrollToLatestMessage(false)}
            ref={listRef}
            renderItem={({ item }) => (
              <MessageBubble
                displayVariant={item.variant}
                isMine={item.message.sender_id === user?.id}
                message={item.message}
                bookingPreview={bookingPreviews[getBookingIdFromMessage(item.message) ?? -1]}
                bookingPayment={bookingPaymentsById[getBookingIdFromMessage(item.message) ?? -1]}
                onBookingPress={() => void handleBookingPress(item.message)}
                onPrimaryAction={(action) => {
                  const bookingId = getBookingIdFromMessage(item.message);
                  if (bookingId) {
                    void handleChatPrimaryAction(
                      bookingId,
                      action,
                      getPaymentStageFromBooking(bookingPreviews[bookingId], item.message),
                    );
                  }
                }}
                isActionLoading={isBookingActionLoading}
                userRole={user?.role}
              />
            )}
          />
        </View>
      )}

      {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

      <View style={styles.inputBar}>
        <TextInput
          multiline
          onChangeText={setInputText}
          placeholder="Message"
          placeholderTextColor={colors.mutedText}
          style={styles.input}
          value={inputText}
        />
        <Pressable
          accessibilityLabel="Send message"
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
            size={20}
          />
        </Pressable>
      </View>

      {user?.role === "provider" ? (
        <ProviderBookingDetailModal
          actionError={bookingActionError}
          booking={selectedBooking}
          finalQuoteAmount={finalQuoteAmount}
          finalQuoteMessage={finalQuoteMessage}
          isActing={isBookingActionLoading}
          onApproveRefund={() => void handleApproveRefund()}
          onClose={closeBookingActionModal}
          onComplete={() => void handleCompleteBooking()}
          onPickCompletionProof={() => void handlePickCompletionProof()}
          onQuote={() => void handleQuoteBooking()}
          onReject={() => setReasonAction("reject_booking")}
          onRejectRefund={() => setReasonAction("reject_refund")}
          onStartVisit={() => void handleStartVisit()}
          onSubmitFinalQuote={() => void handleSubmitFinalQuote()}
          payment={selectedBookingPayment}
          proofAssets={proofAssets}
          quoteFiles={quoteFiles}
          quoteFilesError={quoteFilesError}
          setQuoteFiles={(files) => {
            setQuoteFiles(files);
            setQuoteFilesError("");
          }}
          quoteAmount={quoteAmount}
          quoteAmountError={quoteAmountError}
          quoteMessage={quoteMessage}
          setFinalQuoteAmount={(value) => { setFinalQuoteAmount(value); setBookingActionError(""); }}
          setFinalQuoteMessage={(value) => { setFinalQuoteMessage(value); setBookingActionError(""); }}
          setQuoteAmount={(value) => { setQuoteAmount(value); setQuoteAmountError(""); setBookingActionError(""); }}
          setQuoteMessage={(value) => { setQuoteMessage(value); setBookingActionError(""); }}
          setVisitFeeAmount={(value) => { setVisitFeeAmount(value); setVisitFeeError(""); setBookingActionError(""); }}
          visitFeeAmount={visitFeeAmount}
          visitFeeError={visitFeeError}
        />
      ) : (
        <CustomerBookingDetailModal
          actionError={bookingActionError}
          booking={selectedBooking}
          bookingForm={bookingForm}
          isActing={isBookingActionLoading}
          onAcceptFinalQuote={() => void handleAcceptFinalQuote()}
          onAcceptQuote={() => void handleAcceptQuote()}
          onAppealRefund={() => void handleAppealRefund()}
          onCancel={confirmCancelBooking}
          onCancelAfterVisit={confirmCancelAfterVisit}
          onCancelRefund={confirmCancelRefund}
          onClose={closeBookingActionModal}
          onConfirmComplete={() => void handleConfirmComplete()}
          onPay={() => void handlePayBooking()}
          onRejectFinalQuote={() => setReasonAction("reject_final_quote")}
          onRejectQuote={() => setReasonAction("reject_quote")}
          onRequestRefund={() => setReasonAction("refund")}
          onUpdate={() => void handleUpdateBooking()}
          payment={selectedBookingPayment}
          refundAppealReason={refundAppealReason}
          refundAmount={refundAmount}
          refundReason={refundReason}
          setBookingForm={setBookingForm}
          setRefundAmount={(value) => { setRefundAmount(value); setBookingActionError(""); }}
          setRefundAppealReason={(value) => { setRefundAppealReason(value); setBookingActionError(""); }}
          setRefundReason={(value) => { setRefundReason(value); setBookingActionError(""); }}
        />
      )}

      {selectedBooking && reasonAction ? (
        <ActionReasonModal
          amount={refundAmount}
          amountLabel="Refund amount (optional)"
          confirmLabel={reasonAction === "refund" ? "Request refund" : "Submit"}
          onCancel={() => setReasonAction(null)}
          onChangeAmount={reasonAction === "refund" ? setRefundAmount : undefined}
          onChangeReason={(value) => {
            if (reasonAction === "refund") {
              setRefundReason(value);
            } else if (reasonAction === "reject_booking") {
              setRejectReason(value);
            } else if (reasonAction === "reject_refund") {
              setRefundRejectReason(value);
            } else {
              setQuoteRejectReason(value);
            }
            setBookingActionError("");
          }}
          onConfirm={confirmReasonAction}
          reason={
            reasonAction === "refund"
              ? refundReason
              : reasonAction === "reject_booking"
                ? rejectReason
                : reasonAction === "reject_refund"
                  ? refundRejectReason
                  : quoteRejectReason
          }
          reasonLabel={reasonAction === "refund" ? "Refund reason" : "Reason"}
          title={
            reasonAction === "refund"
              ? "Request a refund"
              : reasonAction === "reject_booking"
                ? "Decline booking"
                : reasonAction === "reject_refund"
                  ? "Reject refund"
                  : reasonAction === "reject_final_quote"
                    ? "Decline final quote"
                    : "Decline quote"
          }
          error={bookingActionError}
        />
      ) : null}

      {confirmationModal}

      <CustomerReviewModal
        booking={reviewBooking}
        errorMessage={reviewError}
        isSubmitting={isSubmittingReview}
        onClose={() => setReviewBooking(null)}
        onSubmit={(rating, comment) => void handleSubmitReview(rating, comment)}
      />

      <BookingRequestModal
        bookingForm={createBookingForm}
        errorMessage={createBookingError}
        isLoading={isCreatingBooking}
        onClose={() => setIsCreateBookingModalVisible(false)}
        onSubmit={() => void handleCreateBookingFromChat()}
        serviceCategories={bookingProvider?.tags ?? []}
        setBookingForm={setCreateBookingForm}
        visible={isCreateBookingModalVisible}
      />
    </KeyboardAvoidingView>
  );
}

function ChatHeaderTitle({
  title,
  isOnline,
}: {
  title: string;
  isOnline: boolean;
}) {
  return (
    <View style={styles.chatHeaderTitle}>
      <Text numberOfLines={1} style={styles.chatHeaderName}>
        {title}
      </Text>
      <View style={styles.chatHeaderStatus}>
        <View
          style={[
            styles.chatHeaderStatusDot,
            isOnline
              ? styles.chatHeaderStatusDotOnline
              : styles.chatHeaderStatusDotOffline,
          ]}
        />
        <Text style={styles.chatHeaderStatusText}>
          {isOnline ? "Online" : "Offline"}
        </Text>
      </View>
    </View>
  );
}

function MessageBubble({
  displayVariant,
  message,
  bookingPreview,
  bookingPayment,
  isMine,
  isPinned = false,
  onBookingPress,
  onPrimaryAction,
  isActionLoading,
  userRole,
}: {
  displayVariant: ChatDisplayItem["variant"];
  message: ChatMessage;
  bookingPreview?: BookingDetail;
  bookingPayment?: PaymentSummary | null;
  isMine: boolean;
  isPinned?: boolean;
  onBookingPress: () => void;
  onPrimaryAction: (action: CustomerBookingListAction) => void;
  isActionLoading: boolean;
  userRole?: string;
}) {
  const isBookingMessage =
    message.related_type === "booking" ||
    message.message_type === "booking_created" ||
    message.message_type === "booking_status";

  return (
    <View
      style={[
        styles.messageRow,
        isMine ? styles.messageRowMine : styles.messageRowOther,
      ]}
    >
      {displayVariant === "booking_update" ? (
        <BookingStatusUpdate message={message} isMine={isMine} />
      ) : displayVariant === "booking" && isBookingMessage ? (
        <BookingMessageCard
          isMine={isMine}
          isPinned={isPinned}
          message={message}
          bookingPreview={bookingPreview}
          bookingPayment={bookingPayment}
          onPress={onBookingPress}
          onPrimaryAction={onPrimaryAction}
          isActionLoading={isActionLoading}
          userRole={userRole}
        />
      ) : (
        <View style={[styles.bubble, isMine ? styles.bubbleMine : styles.bubbleOther]}>
          <Text style={[styles.bubbleText, isMine ? styles.bubbleTextMine : null]}>
            {formatMessageContent(message)}
          </Text>
          <Text style={[styles.messageTime, isMine ? styles.messageTimeMine : null]}>
            {formatMessageTime(message.created_at)}
          </Text>
        </View>
      )}
    </View>
  );
}

function BookingStatusUpdate({
  message,
  isMine,
}: {
  message: ChatMessage;
  isMine: boolean;
}) {
  const metadata = message.metadata ?? {};
  const status =
    typeof metadata.new_status === "string" ? metadata.new_status : "";
  const detail = typeof metadata.detail === "string" ? metadata.detail : "";
  const title =
    typeof metadata.title === "string"
      ? metadata.title
      : status
        ? `Booking update: ${getBookingStatusLabelForChat(status)}`
        : "Booking updated";

  return (
    <View
      style={[
        styles.bookingUpdate,
        isMine ? styles.bookingUpdateMine : styles.bookingUpdateOther,
      ]}
    >
      <Text style={styles.bookingUpdateTitle}>{title}</Text>
      {detail ? <Text style={styles.bookingUpdateDetail}>{detail}</Text> : null}
      <Text style={styles.messageTime}>{formatMessageTime(message.created_at)}</Text>
    </View>
  );
}

function BookingMessageCard({
  message,
  bookingPreview,
  bookingPayment,
  isMine,
  isPinned = false,
  onPress,
  onPrimaryAction,
  isActionLoading,
  userRole,
}: {
  message: ChatMessage;
  bookingPreview?: BookingDetail;
  bookingPayment?: PaymentSummary | null;
  isMine: boolean;
  isPinned?: boolean;
  onPress: () => void;
  onPrimaryAction: (action: CustomerBookingListAction) => void;
  isActionLoading: boolean;
  userRole?: string;
}) {
  const metadata = message.metadata ?? {};
  const title =
    typeof metadata.title === "string"
      ? metadata.title
      : message.message_type === "booking_created"
        ? "New booking request"
        : "Booking updated";
  const serviceDescription =
    typeof metadata.service_description === "string"
      ? metadata.service_description
      : message.message.split("\n").find((line) => line.startsWith("Service:")) || "";
  const address =
    typeof metadata.service_address === "string" ? metadata.service_address : "";
  const startTime =
    typeof metadata.scheduled_start_time === "string"
      ? metadata.scheduled_start_time
      : "";
  const endTime =
    typeof metadata.scheduled_end_time === "string" ? metadata.scheduled_end_time : "";
  const status =
    bookingPreview?.status ||
    (typeof metadata.status === "string"
      ? metadata.status
      : typeof metadata.new_status === "string"
        ? metadata.new_status
        : message.message_type === "booking_created"
          ? "pending"
          : "");
  const quoteAmount =
    typeof metadata.quote_amount === "number"
      ? metadata.quote_amount
      : bookingPreview?.expected_service_amount ?? bookingPreview?.quote_amount ?? null;
  const visitFeeAmount =
    typeof metadata.visit_fee_amount === "number"
      ? metadata.visit_fee_amount
      : bookingPreview?.visit_fee_amount ?? null;
  const finalQuoteAmount =
    typeof metadata.final_quote_amount === "number"
      ? metadata.final_quote_amount
      : bookingPreview?.final_quote_amount ?? null;
  const initialQuoteMessage =
    typeof metadata.quote_message === "string"
      ? metadata.quote_message
      : bookingPreview?.quote_message || "";
  const finalQuoteMessage =
    typeof metadata.final_quote_message === "string"
      ? metadata.final_quote_message
      : bookingPreview?.final_quote_message || "";
  const quoteMessage =
    finalQuoteAmount != null && finalQuoteMessage
      ? finalQuoteMessage
      : initialQuoteMessage;
  const paymentStatus =
    bookingPayment?.status ||
    (typeof metadata.payment_status === "string"
      ? metadata.payment_status
      : null);
  const primaryAction =
    userRole === "customer"
      ? getCustomerBookingListAction(
          { status },
          paymentStatus ? { status: paymentStatus } : null,
        )
      : null;
  const canOpenOrder = isBookingVisibleInActiveBookings(status, userRole);
  const payableAmount =
    status === "awaiting_service_payment"
      ? finalQuoteAmount ?? quoteAmount
      : visitFeeAmount ?? quoteAmount;

  return (
    <Pressable
      accessibilityRole={canOpenOrder ? "button" : undefined}
      disabled={!canOpenOrder}
      onPress={canOpenOrder ? onPress : undefined}
      style={({ pressed }) => [
        styles.bookingCard,
        isPinned ? styles.bookingCardPinned : null,
        isMine ? styles.bookingCardMine : null,
        pressed ? styles.bookingCardPressed : null,
      ]}
    >
      <View style={styles.bookingTopRow}>
        <Text style={styles.bookingTitle}>{title}</Text>
        {status ? (
          <View style={styles.statusPill}>
            <Text style={styles.statusText}>{getBookingStatusLabelForChat(status)}</Text>
          </View>
        ) : null}
      </View>
      <Text numberOfLines={2} style={styles.bookingDescription}>
        {serviceDescription.replace("Service:", "").trim() || "Booking details"}
      </Text>
      {address ? (
        <View style={styles.bookingMetaRow}>
          <MapPin color={colors.mutedText} size={14} />
          <Text numberOfLines={1} style={styles.bookingMetaText}>
            {address}
          </Text>
        </View>
      ) : null}
      {startTime || endTime ? (
        <View style={styles.bookingMetaRow}>
          <CalendarClock color={colors.mutedText} size={14} />
          <Text numberOfLines={1} style={styles.bookingMetaText}>
            {formatShortDateTime(startTime)} - {formatShortDateTime(endTime)}
          </Text>
        </View>
      ) : null}
      {quoteAmount != null || visitFeeAmount != null ? (
        <Text style={styles.bookingQuoteText}>
          {status === "awaiting_service_payment" ? "Service amount" : "Visit fee"}: {formatMoney(payableAmount)}
        </Text>
      ) : null}
      {quoteMessage ? (
        <Text numberOfLines={2} style={styles.bookingQuoteMessage}>
          {quoteMessage}
        </Text>
      ) : null}
      {canOpenOrder ? <Text style={styles.bookingHint}>Tap to view booking</Text> : null}
      {primaryAction ? (
        <Pressable
          accessibilityRole="button"
          disabled={isActionLoading}
          onPress={() => onPrimaryAction(primaryAction)}
          style={styles.bookingPayButton}
        >
          {isActionLoading ? (
            <ActivityIndicator color="#FFFFFF" size="small" />
          ) : (
            <Text style={styles.bookingPayButtonText}>
              {primaryAction === "accept_quote"
                ? "Accept quote"
                : primaryAction === "accept_final_quote"
                  ? "Accept final quote"
                  : primaryAction === "confirm_complete"
                    ? "Confirm complete"
                    : paymentStatus === "checkout_created"
                      ? "Continue payment"
                      : formatPayLabel(
                          status === "awaiting_service_payment"
                            ? finalQuoteAmount ?? quoteAmount
                            : visitFeeAmount ?? quoteAmount,
                        )}
            </Text>
          )}
        </Pressable>
      ) : null}
      <Text style={styles.messageTime}>{formatMessageTime(message.created_at)}</Text>
    </Pressable>
  );
}


function createBookingFormFromDetail(
  booking: BookingDetail,
): BookingRequestFormState {
  return {
    title: booking.title,
    serviceCategory: booking.service_category ?? "",
    serviceDescription: booking.service_description,
    serviceAddress: booking.service_address,
    scheduledStartTime: toEditableDateTime(booking.scheduled_start_time),
    scheduledEndTime: toEditableDateTime(booking.scheduled_end_time),
    attachments: [],
  };
}

function buildUpdatePayload(
  booking: BookingDetail,
  form: BookingRequestFormState,
): BookingPayload | null {
  if (
    !form.title.trim() ||
    form.title.trim().split(/\s+/).length > 30 ||
    !form.serviceDescription.trim() ||
    !form.serviceAddress.trim() ||
    !form.scheduledStartTime.trim() ||
    !form.scheduledEndTime.trim()
  ) {
    return null;
  }

  return {
    service_category: booking.service_category ?? "",
    title: form.title.trim(),
    service_description: form.serviceDescription.trim(),
    service_address: form.serviceAddress.trim(),
    service_latitude: booking.service_latitude,
    service_longitude: booking.service_longitude,
    customer_current_address: booking.customer_current_address,
    customer_current_latitude: booking.customer_current_latitude,
    customer_current_longitude: booking.customer_current_longitude,
    scheduled_start_time: form.scheduledStartTime.trim(),
    scheduled_end_time: form.scheduledEndTime.trim(),
  };
}

function parseWebSocketMessage(value: unknown) {
  if (typeof value !== "string") {
    return null;
  }

  try {
    const data = JSON.parse(value);
    return data && typeof data === "object"
      ? (data as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function isIncomingChatMessage(value: unknown): value is ChatMessage {
  return (
    Boolean(value) &&
    typeof value === "object" &&
    typeof (value as ChatMessage).id === "number" &&
    typeof (value as ChatMessage).chat_room_id === "number" &&
    typeof (value as ChatMessage).sender_id === "number"
  );
}

function appendChatMessageWithoutDuplicate(
  currentMessages: ChatMessage[],
  nextMessage: ChatMessage,
) {
  if (currentMessages.some((message) => message.id === nextMessage.id)) {
    return currentMessages;
  }

  return [...currentMessages, nextMessage];
}

function collapseBookingMessages(messages: ChatMessage[]): ChatDisplayItem[] {
  const result: ChatDisplayItem[] = [];
  const bookingCardIndexes = new Map<number, number>();

  for (const message of messages) {
    if (!isBookingMessage(message)) {
      result.push({
        key: `message-${message.id}`,
        message,
        variant: "message",
      });
      continue;
    }

    const bookingId = getBookingIdFromMessage(message);
    if (!bookingId) {
      result.push({
        key: `message-${message.id}`,
        message,
        variant: "message",
      });
      continue;
    }

    const existingCardIndex = bookingCardIndexes.get(bookingId);
    if (existingCardIndex === undefined) {
      result.push({
        key: `booking-${bookingId}`,
        message,
        variant: "booking",
      });
      bookingCardIndexes.set(bookingId, result.length - 1);
      continue;
    }

    const existingCard = result[existingCardIndex];
    if (existingCard.variant === "booking") {
      existingCard.message = {
        ...existingCard.message,
        metadata: mergeBookingPreviewMetadata(
          existingCard.message.metadata,
          message.metadata,
        ),
      };
    }

    result.push({
      key: `booking-update-${message.id}`,
      message,
      variant: "booking_update",
    });
  }

  return result;
}

function isBookingMessage(message: ChatMessage) {
  return (
    message.related_type === "booking" ||
    message.message_type === "booking_created" ||
    message.message_type === "booking_status"
  );
}

function mergeBookingPreviewMetadata(
  current: Record<string, unknown> | null,
  next: Record<string, unknown> | null,
) {
  const merged = { ...(current ?? {}) };
  const latest = next ?? {};
  const latestStatus =
    typeof latest.new_status === "string"
      ? latest.new_status
      : typeof latest.status === "string"
        ? latest.status
        : null;

  for (const key of [
    "quote_amount",
    "expected_service_amount",
    "visit_fee_amount",
    "final_quote_amount",
    "final_quote_message",
    "quote_message",
    "quoted_at",
    "currency",
    "amount",
    "payment_id",
    "payment_status",
    "paid_at",
    "refund_request_id",
    "refund_status",
    "provider_note",
    "appeal_reason",
    "completed_at",
  ]) {
    if (key in latest) {
      merged[key] = latest[key];
    }
  }

  if (latestStatus) {
    merged.status = latestStatus;
  }

  return merged;
}

function getLatestBookingCardItem(
  items: ChatDisplayItem[],
  bookingPreviews: Record<number, BookingDetail>,
) {
  const bookingCards = new Map<number, ChatDisplayItem>();

  for (const item of items) {
    if (item.variant !== "booking") {
      continue;
    }

    const bookingId = getBookingIdFromMessage(item.message);
    if (bookingId) {
      bookingCards.set(bookingId, item);
    }
  }

  let latestActivity: { item: ChatDisplayItem; timestamp: number } | null = null;

  for (const item of items) {
    const bookingId = getBookingIdFromMessage(item.message);
    if (!bookingId) {
      continue;
    }

    const bookingCard = bookingCards.get(bookingId);
    const messageStatus = bookingCard
      ? getBookingPreviewStatus(bookingCard.message)
      : "";
    const currentStatus = bookingPreviews[bookingId]?.status;
    if (
      bookingCard &&
      shouldShowBookingInChat(messageStatus) &&
      shouldShowBookingInChat(currentStatus)
    ) {
      const timestamp = Date.parse(item.message.created_at);
      if (!latestActivity || timestamp >= latestActivity.timestamp) {
        latestActivity = {
          item: bookingCard,
          timestamp: Number.isNaN(timestamp) ? 0 : timestamp,
        };
      }
    }
  }

  return latestActivity?.item ?? null;
}

function getBookingPreviewStatus(message: ChatMessage) {
  const metadata = message.metadata ?? {};

  if (typeof metadata.status === "string") {
    return metadata.status;
  }

  if (typeof metadata.new_status === "string") {
    return metadata.new_status;
  }

  return "";
}

function getBookingIdFromMessage(message: ChatMessage) {
  if (message.related_type === "booking" && message.related_id) {
    return message.related_id;
  }

  const bookingId = message.metadata?.booking_id;

  if (typeof bookingId === "number") {
    return bookingId;
  }

  if (typeof bookingId === "string") {
    const parsed = Number(bookingId);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function getPaymentStageFromMessage(message: ChatMessage): "visit_fee" | "service_fee" {
  return getBookingPreviewStatus(message) === "awaiting_service_payment"
    ? "service_fee"
    : "visit_fee";
}

function getPaymentStageFromBooking(
  booking: BookingDetail | undefined,
  message: ChatMessage,
): "visit_fee" | "service_fee" {
  return booking
    ? booking.status === "awaiting_service_payment"
      ? "service_fee"
      : "visit_fee"
    : getPaymentStageFromMessage(message);
}

function formatMessageContent(message: ChatMessage) {
  if (message.attachments.length > 0 || message.message_type === "attachment") {
    const hasPicture = message.attachments.some((attachment) =>
      attachment.content_type.startsWith("image/"),
    );

    return hasPicture ? "[picture]" : "[file]";
  }

  return message.message || " ";
}

function isBookingVisibleInActiveBookings(
  status: string,
  userRole?: string,
) {
  return (
    (userRole === "customer" || userRole === "provider") &&
    Boolean(status) &&
    shouldShowBookingInChat(status)
  );
}

function isBookingVisibleInActiveBookingsForDetail(
  booking: BookingDetail,
  userRole?: string,
) {
  return isBookingVisibleInActiveBookings(String(booking.status), userRole);
}

function formatMessageTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  headerOrderButton: {
    minHeight: 34,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
  },
  headerOrderButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "800",
  },
  centerBox: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    padding: spacing.lg,
  },
  centerText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  chatHeaderTitle: {
    maxWidth: 220,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  chatHeaderName: {
    maxWidth: 132,
    color: colors.text,
    fontSize: 17,
    fontWeight: "800",
  },
  chatHeaderStatus: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  chatHeaderStatusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  chatHeaderStatusDotOnline: {
    backgroundColor: colors.primary,
  },
  chatHeaderStatusDotOffline: {
    backgroundColor: "#A0A4AE",
  },
  chatHeaderStatusText: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: "700",
  },
  chatArea: {
    flex: 1,
  },
  pinnedBookingLayer: {
    position: "absolute",
    top: spacing.sm,
    left: spacing.md,
    right: spacing.md,
    zIndex: 20,
    elevation: 8,
  },
  messageList: {
    flexGrow: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  messageListWithPinnedBooking: {
    paddingBottom: 188,
  },
  emptyBox: {
    flex: 1,
    minHeight: 260,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 15,
  },
  messageRow: {
    flexDirection: "row",
  },
  messageRowMine: {
    justifyContent: "flex-end",
  },
  messageRowOther: {
    justifyContent: "flex-start",
  },
  bubble: {
    maxWidth: "78%",
    gap: spacing.xs,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  bubbleMine: {
    backgroundColor: colors.primary,
  },
  bubbleOther: {
    backgroundColor: colors.surface,
  },
  bubbleText: {
    color: colors.text,
    fontSize: 16,
    lineHeight: 22,
  },
  bubbleTextMine: {
    color: "#FFFFFF",
  },
  messageTime: {
    alignSelf: "flex-end",
    color: colors.mutedText,
    fontSize: 11,
  },
  messageTimeMine: {
    color: "rgba(255, 255, 255, 0.75)",
  },
  bookingCard: {
    width: "82%",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  bookingCardPinned: {
    width: "100%",
    shadowColor: "#000000",
    shadowOffset: {
      width: 0,
      height: 8,
    },
    shadowOpacity: 0.12,
    shadowRadius: 18,
  },
  bookingCardMine: {
    backgroundColor: "#E8F7F2",
    borderColor: "#B7E4D5",
  },
  bookingCardPressed: {
    opacity: 0.76,
  },
  bookingTopRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  bookingTitle: {
    flex: 1,
    color: colors.text,
    fontSize: 15,
    fontWeight: "800",
  },
  bookingDescription: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  bookingQuoteText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800",
  },
  bookingQuoteMessage: {
    color: colors.mutedText,
    fontSize: 12,
    lineHeight: 18,
  },
  bookingMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  bookingMetaText: {
    flex: 1,
    color: colors.mutedText,
    fontSize: 12,
  },
  bookingHint: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
  },
  bookingUpdate: {
    maxWidth: "82%",
    gap: spacing.xs,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  bookingUpdateMine: {
    backgroundColor: "#E8F7F2",
  },
  bookingUpdateOther: {
    backgroundColor: colors.surface,
  },
  bookingUpdateTitle: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
  },
  bookingUpdateDetail: {
    color: colors.mutedText,
    fontSize: 12,
    lineHeight: 18,
  },
  bookingPayButton: {
    minHeight: 36,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
  },
  bookingPayButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "800",
  },
  statusPill: {
    borderRadius: 999,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  statusText: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: "800",
  },
  errorText: {
    color: colors.danger,
    fontSize: 13,
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.xs,
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
    maxHeight: 120,
    minHeight: 44,
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
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.primary,
  },
  sendButtonDisabled: {
    backgroundColor: colors.surface,
  },
  modalOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0, 0, 0, 0.28)",
  },
  modalCard: {
    maxHeight: "92%",
    gap: spacing.md,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  modalTitle: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "800",
  },
  modalErrorText: {
    color: colors.danger,
    fontSize: 13,
    lineHeight: 19,
  },
  payHint: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 19,
  },
  modalScrollContent: {
    gap: spacing.md,
    paddingBottom: spacing.sm,
  },
  detailBox: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  detailLabel: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: "700",
  },
  detailValue: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  stageBox: {
    gap: spacing.sm,
  },
  stageOptions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  stageButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  stageButtonActive: {
    borderColor: colors.primary,
    backgroundColor: "#ECFDF3",
  },
  stageButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  stageButtonTextActive: {
    color: colors.primary,
  },
  proofBox: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  proofText: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  proofFileList: {
    gap: spacing.xs,
  },
  proofFileText: {
    color: colors.text,
    fontSize: 13,
    lineHeight: 18,
  },
  noActionText: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  modalActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
});
