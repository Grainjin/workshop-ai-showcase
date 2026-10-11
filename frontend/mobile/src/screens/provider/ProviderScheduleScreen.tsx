import { ChevronLeft, ChevronRight, Clock } from "lucide-react-native";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";

import {
  deleteProviderAvailabilityOverride,
  getProviderAvailability,
  getProviderAvailabilityOverrides,
  getProviderScheduleBookings,
  updateProviderAvailability,
  updateProviderAvailabilityOverride,
} from "../../api/provider";
import { PrimaryButton } from "../../components/PrimaryButton";
import { ScreenContainer } from "../../components/ScreenContainer";
import { SecondaryButton } from "../../components/SecondaryButton";
import { BookingPriceBreakdown } from "../../components/BookingPriceBreakdown";
import { BookingContextInformation } from "../../components/BookingContextInformation";
import { ProviderBookingDetailModal } from "../../components/ProviderBookingDetailModal";
import { TextField } from "../../components/TextField";
import { colors, radius, spacing } from "../../theme/theme";
import type { BookingDetail } from "../../types/booking";
import type {
  ProviderAvailability,
  ProviderAvailabilityOverride,
} from "../../types/provider";
import { getErrorMessage } from "../../utils/errors";

type ScheduleTab = "availability" | "jobs";

const WEEKDAYS = [
  { value: 1, label: "Mon" },
  { value: 2, label: "Tue" },
  { value: 3, label: "Wed" },
  { value: 4, label: "Thu" },
  { value: 5, label: "Fri" },
  { value: 6, label: "Sat" },
  { value: 7, label: "Sun" },
];

export function ProviderScheduleScreen() {
  const [activeTab, setActiveTab] = useState<ScheduleTab>("availability");
  const [monthDate, setMonthDate] = useState(() => startOfMonth(new Date()));
  const [availabilities, setAvailabilities] = useState<ProviderAvailability[]>([]);
  const [overrides, setOverrides] = useState<ProviderAvailabilityOverride[]>([]);
  const [scheduleBookings, setScheduleBookings] = useState<BookingDetail[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [defaultModalVisible, setDefaultModalVisible] = useState(false);
  const [dayModalVisible, setDayModalVisible] = useState(false);
  const [jobListModalVisible, setJobListModalVisible] = useState(false);
  const [jobDetailModalVisible, setJobDetailModalVisible] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedJobDate, setSelectedJobDate] = useState<string | null>(null);
  const [selectedBooking, setSelectedBooking] = useState<BookingDetail | null>(null);
  const [defaultStartTime, setDefaultStartTime] = useState("08:00");
  const [defaultEndTime, setDefaultEndTime] = useState("20:00");
  const [defaultWeekdays, setDefaultWeekdays] = useState<number[]>([]);
  const [dayStartTime, setDayStartTime] = useState("08:00");
  const [dayEndTime, setDayEndTime] = useState("20:00");
  const [dayUnavailable, setDayUnavailable] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const monthKey = formatMonthKey(monthDate);
  const todayKey = useMemo(() => formatDateKey(new Date()), []);
  const currentMonthDate = useMemo(() => startOfMonth(new Date()), []);
  const canGoPreviousMonth = compareMonths(monthDate, currentMonthDate) > 0;

  useEffect(() => {
    let isMounted = true;

    async function loadSchedule() {
      setIsLoading(true);
      setMessage("");

      try {
        const availabilityData = await getProviderAvailability();
        const overrideData = await getProviderAvailabilityOverrides(monthKey);

        if (!isMounted) {
          return;
        }

        const nextAvailabilities = availabilityData?.availabilities ?? [];
        setAvailabilities(nextAvailabilities);
        setOverrides(overrideData ?? []);
        syncDefaultForm(
          nextAvailabilities,
          setDefaultStartTime,
          setDefaultEndTime,
          setDefaultWeekdays,
        );
      } catch (error) {
        if (isMounted) {
          setMessage(getErrorMessage(error));
        }
      }

      try {
        const bookingData = await getProviderScheduleBookings(monthKey);

        if (isMounted) {
          setScheduleBookings(bookingData ?? []);
        }
      } catch {
        if (isMounted) {
          setScheduleBookings([]);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadSchedule();

    return () => {
      isMounted = false;
    };
  }, [monthKey]);

  const calendarDays = useMemo(() => buildCalendarDays(monthDate), [monthDate]);
  const selectedDateBookings = useMemo(() => {
    if (!selectedJobDate) {
      return [];
    }

    return getBookingsForDate(selectedJobDate, scheduleBookings);
  }, [selectedJobDate, scheduleBookings]);

  async function refreshOverrides() {
    const nextOverrides = await getProviderAvailabilityOverrides(monthKey);
    setOverrides(nextOverrides ?? []);
  }

  async function handleSaveDefaultAvailability() {
    setIsSaving(true);
    setMessage("");

    try {
      const payload = defaultWeekdays.map((weekday) => ({
        weekday,
        start_time: defaultStartTime,
        end_time: defaultEndTime,
        is_available: true,
      }));
      const result = await updateProviderAvailability(payload);
      const nextAvailabilities = result?.availabilities ?? [];

      setAvailabilities(nextAvailabilities);
      syncDefaultForm(nextAvailabilities, setDefaultStartTime, setDefaultEndTime, setDefaultWeekdays);
      setDefaultModalVisible(false);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  function openDayModal(day: CalendarDay) {
    if (!day.dateKey) {
      return;
    }

    if (day.dateKey < todayKey) {
      setMessage("Past dates cannot be edited.");
      return;
    }

    const override = getOverrideForDate(day.dateKey, overrides);
    const defaultAvailability = getAvailabilityForWeekday(
      getIsoWeekday(parseDateKey(day.dateKey)),
      availabilities,
    );

    setSelectedDate(day.dateKey);
    setDayStartTime(override?.start_time || defaultAvailability?.start_time || "08:00");
    setDayEndTime(override?.end_time || defaultAvailability?.end_time || "20:00");
    setDayUnavailable(
      override ? !override.is_available : !Boolean(defaultAvailability?.is_available),
    );
    setDayModalVisible(true);
  }

  async function handleSaveDayOverride() {
    if (!selectedDate) {
      return;
    }

    setIsSaving(true);
    setMessage("");

    try {
      await updateProviderAvailabilityOverride(selectedDate, {
        start_time: dayUnavailable ? null : dayStartTime,
        end_time: dayUnavailable ? null : dayEndTime,
        is_available: !dayUnavailable,
      });
      await refreshOverrides();
      setDayModalVisible(false);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleClearDayOverride() {
    if (!selectedDate) {
      return;
    }

    setIsSaving(true);
    setMessage("");

    try {
      await deleteProviderAvailabilityOverride(selectedDate);
      await refreshOverrides();
      setDayModalVisible(false);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  function openJobListModal(day: CalendarDay) {
    if (!day.dateKey) {
      return;
    }

    const dayBookings = getBookingsForDate(day.dateKey, scheduleBookings);
    if (dayBookings.length === 0) {
      return;
    }

    setSelectedJobDate(day.dateKey);
    setJobListModalVisible(true);
  }

  function openBookingDetail(booking: BookingDetail) {
    setSelectedBooking(booking);
    setJobDetailModalVisible(true);
  }

  return (
    <ScreenContainer contentStyle={styles.content}>
      <View style={styles.tabRow}>
        <SegmentButton
          isActive={activeTab === "availability"}
          label="Hours"
          onPress={() => setActiveTab("availability")}
        />
        <SegmentButton
          isActive={activeTab === "jobs"}
          label="Upcoming bookings"
          onPress={() => setActiveTab("jobs")}
        />
      </View>

      {message ? <Text style={styles.errorText}>{message}</Text> : null}

      {activeTab === "availability" ? (
        <View style={styles.section}>
          <Pressable
            accessibilityRole="button"
            onPress={() => setDefaultModalVisible(true)}
            style={styles.defaultCard}
          >
            <View style={styles.defaultIconBox}>
              <Clock color={colors.primary} size={22} />
            </View>
            <View style={styles.defaultTextBox}>
              <Text style={styles.cardTitle}>Default work hours</Text>
              <Text style={styles.cardText}>
                {defaultWeekdays.map(getWeekdayLabel).join(", ") || "No workdays set"}
              </Text>
              <Text style={styles.cardText}>
                {defaultWeekdays.length > 0
                  ? `${defaultStartTime} - ${defaultEndTime}`
                  : "No default hours set"}
              </Text>
            </View>
            <Text style={styles.linkText}>Edit</Text>
          </Pressable>

          <View style={styles.calendarCard}>
            <View style={styles.calendarHeader}>
              <Pressable
                accessibilityRole="button"
                disabled={!canGoPreviousMonth}
                onPress={() => {
                  if (canGoPreviousMonth) {
                    setMonthDate(addMonths(monthDate, -1));
                  }
                }}
                style={[
                  styles.monthButton,
                  !canGoPreviousMonth ? styles.monthButtonDisabled : null,
                ]}
              >
                <ChevronLeft
                  color={canGoPreviousMonth ? colors.text : colors.border}
                  size={20}
                />
              </Pressable>
              <Text style={styles.monthTitle}>{formatMonthTitle(monthDate)}</Text>
              <Pressable
                accessibilityRole="button"
                onPress={() => setMonthDate(addMonths(monthDate, 1))}
                style={styles.monthButton}
              >
                <ChevronRight color={colors.text} size={20} />
              </Pressable>
            </View>

            <View style={styles.weekdayHeaderRow}>
              {WEEKDAYS.map((weekday) => (
                <Text key={weekday.value} style={styles.weekdayHeaderText}>
                  {weekday.label}
                </Text>
              ))}
            </View>

            {isLoading ? (
              <View style={styles.loadingBox}>
                <ActivityIndicator color={colors.primary} />
                <Text style={styles.cardText}>Loading schedule...</Text>
              </View>
            ) : (
              <View style={styles.calendarGrid}>
                {calendarDays.map((day, index) => (
                  <CalendarDayCell
                    availabilities={availabilities}
                    day={day}
                    key={day.dateKey || `blank-${index}`}
                    onPress={() => openDayModal(day)}
                    overrides={overrides}
                    todayKey={todayKey}
                  />
                ))}
              </View>
            )}
          </View>
        </View>
      ) : (
        <View style={styles.section}>
          <View style={styles.calendarCard}>
            <View style={styles.calendarHeader}>
              <Pressable
                accessibilityRole="button"
                disabled={!canGoPreviousMonth}
                onPress={() => {
                  if (canGoPreviousMonth) {
                    setMonthDate(addMonths(monthDate, -1));
                  }
                }}
                style={[
                  styles.monthButton,
                  !canGoPreviousMonth ? styles.monthButtonDisabled : null,
                ]}
              >
                <ChevronLeft
                  color={canGoPreviousMonth ? colors.text : colors.border}
                  size={20}
                />
              </Pressable>
              <Text style={styles.monthTitle}>{formatMonthTitle(monthDate)}</Text>
              <Pressable
                accessibilityRole="button"
                onPress={() => setMonthDate(addMonths(monthDate, 1))}
                style={styles.monthButton}
              >
                <ChevronRight color={colors.text} size={20} />
              </Pressable>
            </View>

            <View style={styles.weekdayHeaderRow}>
              {WEEKDAYS.map((weekday) => (
                <Text key={weekday.value} style={styles.weekdayHeaderText}>
                  {weekday.label}
                </Text>
              ))}
            </View>

            {isLoading ? (
              <View style={styles.loadingBox}>
                <ActivityIndicator color={colors.primary} />
                <Text style={styles.cardText}>Loading upcoming bookings...</Text>
              </View>
            ) : (
              <View style={styles.calendarGrid}>
                {calendarDays.map((day, index) => (
                  <JobCalendarDayCell
                    day={day}
                    key={day.dateKey || `job-blank-${index}`}
                    onPress={() => openJobListModal(day)}
                    scheduleBookings={scheduleBookings}
                  />
                ))}
              </View>
            )}
          </View>
        </View>
      )}

      <DefaultAvailabilityModal
        defaultEndTime={defaultEndTime}
        defaultStartTime={defaultStartTime}
        defaultWeekdays={defaultWeekdays}
        isLoading={isSaving}
        onClose={() => setDefaultModalVisible(false)}
        onSave={() => void handleSaveDefaultAvailability()}
        setDefaultEndTime={setDefaultEndTime}
        setDefaultStartTime={setDefaultStartTime}
        setDefaultWeekdays={setDefaultWeekdays}
        visible={defaultModalVisible}
      />

      <DayAvailabilityModal
        dayEndTime={dayEndTime}
        dayStartTime={dayStartTime}
        dayUnavailable={dayUnavailable}
        hasOverride={Boolean(selectedDate && getOverrideForDate(selectedDate, overrides))}
        isLoading={isSaving}
        onClear={() => void handleClearDayOverride()}
        onClose={() => setDayModalVisible(false)}
        onSave={() => void handleSaveDayOverride()}
        selectedDate={selectedDate}
        setDayEndTime={setDayEndTime}
        setDayStartTime={setDayStartTime}
        setDayUnavailable={setDayUnavailable}
        visible={dayModalVisible}
      />

      <JobListModal
        bookings={selectedDateBookings}
        onClose={() => setJobListModalVisible(false)}
        onOpenBooking={openBookingDetail}
        selectedDate={selectedJobDate}
        visible={jobListModalVisible}
      />

      <ProviderBookingDetailModal
        booking={selectedBooking}
        onClose={() => setJobDetailModalVisible(false)}
        showReadOnly
        visible={jobDetailModalVisible}
      />
    </ScreenContainer>
  );
}

function SegmentButton({
  label,
  isActive,
  onPress,
}: {
  label: string;
  isActive: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={[styles.segmentButton, isActive ? styles.segmentButtonActive : null]}
    >
      <Text style={[styles.segmentText, isActive ? styles.segmentTextActive : null]}>
        {label}
      </Text>
    </Pressable>
  );
}

function DefaultAvailabilityModal({
  visible,
  defaultStartTime,
  defaultEndTime,
  defaultWeekdays,
  isLoading,
  onClose,
  onSave,
  setDefaultStartTime,
  setDefaultEndTime,
  setDefaultWeekdays,
}: {
  visible: boolean;
  defaultStartTime: string;
  defaultEndTime: string;
  defaultWeekdays: number[];
  isLoading: boolean;
  onClose: () => void;
  onSave: () => void;
  setDefaultStartTime: (value: string) => void;
  setDefaultEndTime: (value: string) => void;
  setDefaultWeekdays: (value: number[]) => void;
}) {
  function toggleWeekday(weekday: number) {
    if (defaultWeekdays.includes(weekday)) {
      setDefaultWeekdays(defaultWeekdays.filter((item) => item !== weekday));
      return;
    }

    setDefaultWeekdays([...defaultWeekdays, weekday].sort());
  }

  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible={visible}>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>Default work hours</Text>
          <TextField
            label="Start time"
            onChangeText={setDefaultStartTime}
            placeholder="08:00"
            value={defaultStartTime}
          />
          <TextField
            label="End time"
            onChangeText={setDefaultEndTime}
            placeholder="20:00"
            value={defaultEndTime}
          />
          <Text style={styles.fieldLabel}>Default workdays</Text>
          <Text style={styles.cardText}>
            Select at least one workday. Unselected days are treated as unavailable.
          </Text>
          <View style={styles.weekdayChipGrid}>
            {WEEKDAYS.map((weekday) => {
              const isSelected = defaultWeekdays.includes(weekday.value);

              return (
                <Pressable
                  accessibilityRole="button"
                  key={weekday.value}
                  onPress={() => toggleWeekday(weekday.value)}
                  style={[
                    styles.weekdayChip,
                    isSelected ? styles.weekdayChipSelected : null,
                  ]}
                >
                  <Text
                    style={[
                      styles.weekdayChipText,
                      isSelected ? styles.weekdayChipTextSelected : null,
                    ]}
                  >
                    {weekday.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <View style={styles.modalActions}>
            <SecondaryButton disabled={isLoading} label="Cancel" onPress={onClose} />
            <PrimaryButton
              disabled={isLoading || defaultWeekdays.length === 0}
              isLoading={isLoading}
              label="Save"
              onPress={onSave}
            />
          </View>
        </View>
      </View>
    </Modal>
  );
}

function DayAvailabilityModal({
  visible,
  selectedDate,
  dayStartTime,
  dayEndTime,
  dayUnavailable,
  hasOverride,
  isLoading,
  onClose,
  onSave,
  onClear,
  setDayStartTime,
  setDayEndTime,
  setDayUnavailable,
}: {
  visible: boolean;
  selectedDate: string | null;
  dayStartTime: string;
  dayEndTime: string;
  dayUnavailable: boolean;
  hasOverride: boolean;
  isLoading: boolean;
  onClose: () => void;
  onSave: () => void;
  onClear: () => void;
  setDayStartTime: (value: string) => void;
  setDayEndTime: (value: string) => void;
  setDayUnavailable: (value: boolean) => void;
}) {
  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible={visible}>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>{selectedDate || "Day settings"}</Text>
          <View style={styles.switchRow}>
            <View style={styles.defaultTextBox}>
              <Text style={styles.cardTitle}>Unavailable this day</Text>
              <Text style={styles.cardText}>When saved, this day cannot be booked.</Text>
            </View>
            <Switch
              onValueChange={setDayUnavailable}
              thumbColor={dayUnavailable ? colors.primary : "#FFFFFF"}
              trackColor={{ false: colors.border, true: "#B7E4D5" }}
              value={dayUnavailable}
            />
          </View>
          {!dayUnavailable ? (
            <>
              <TextField
                label="Start time"
                onChangeText={setDayStartTime}
                placeholder="08:00"
                value={dayStartTime}
              />
              <TextField
                label="End time"
                onChangeText={setDayEndTime}
                placeholder="20:00"
                value={dayEndTime}
              />
            </>
          ) : null}
          <View style={styles.modalActions}>
            <SecondaryButton disabled={isLoading} label="Close" onPress={onClose} />
            {hasOverride ? (
              <SecondaryButton
                disabled={isLoading}
                label="Clear"
                onPress={onClear}
              />
            ) : null}
            <PrimaryButton
              disabled={isLoading}
              isLoading={isLoading}
              label="Save"
              onPress={onSave}
            />
          </View>
        </View>
      </View>
    </Modal>
  );
}

function JobCalendarDayCell({
  day,
  scheduleBookings,
  onPress,
}: {
  day: CalendarDay;
  scheduleBookings: BookingDetail[];
  onPress: () => void;
}) {
  if (!day.dateKey || !day.dayNumber) {
    return <View style={styles.dayCell} />;
  }

  const dayBookings = getBookingsForDate(day.dateKey, scheduleBookings);
  const hasJobs = dayBookings.length > 0;

  return (
    <Pressable
      accessibilityRole="button"
      disabled={!hasJobs}
      onPress={onPress}
      style={[
        styles.dayCell,
        hasJobs ? styles.jobDayCellActive : styles.jobDayCellInactive,
      ]}
    >
      <Text style={styles.dayNumber}>{day.dayNumber}</Text>
      <Text numberOfLines={1} style={styles.dayTimeText}>
        {hasJobs ? `${dayBookings.length} bookings` : "No jobs"}
      </Text>
    </Pressable>
  );
}

function JobListModal({
  visible,
  selectedDate,
  bookings,
  onClose,
  onOpenBooking,
}: {
  visible: boolean;
  selectedDate: string | null;
  bookings: BookingDetail[];
  onClose: () => void;
  onOpenBooking: (booking: BookingDetail) => void;
}) {
  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible={visible}>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>{selectedDate || "Bookings for this day"}</Text>
          <ScrollView contentContainerStyle={styles.jobListContent}>
            {bookings.map((booking) => (
              <Pressable
                accessibilityRole="button"
                key={booking.id}
                onPress={() => onOpenBooking(booking)}
                style={styles.jobPreviewCard}
              >
                <View style={styles.jobPreviewHeader}>
                  <Text style={styles.jobPreviewTitle}>Booking #{booking.id}</Text>
                  <Text style={styles.jobStatusBadge}>
                    {getBookingStatusLabel(booking.status)}
                  </Text>
                </View>
                <View style={styles.descriptionFadeBox}>
                  <Text numberOfLines={3} style={styles.jobDescription}>
                    {booking.service_description}
                  </Text>
                  <View pointerEvents="none" style={styles.descriptionFade} />
                </View>
                <Text style={styles.cardText}>
                  {formatShortDateTime(booking.scheduled_start_time)} -{" "}
                  {formatShortDateTime(booking.scheduled_end_time)}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
          <View style={styles.modalActions}>
            <SecondaryButton label="Close" onPress={onClose} />
          </View>
        </View>
      </View>
    </Modal>
  );
}


function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

type CalendarDay = {
  dateKey: string | null;
  dayNumber: number | null;
};

function CalendarDayCell({
  day,
  availabilities,
  overrides,
  todayKey,
  onPress,
}: {
  day: CalendarDay;
  availabilities: ProviderAvailability[];
  overrides: ProviderAvailabilityOverride[];
  todayKey: string;
  onPress: () => void;
}) {
  if (!day.dateKey || !day.dayNumber) {
    return <View style={styles.dayCell} />;
  }

  const isPastDay = day.dateKey < todayKey;
  const override = getOverrideForDate(day.dateKey, overrides);
  const defaultAvailability = getAvailabilityForWeekday(
    getIsoWeekday(parseDateKey(day.dateKey)),
    availabilities,
  );
  const isAvailable = override
    ? override.is_available
    : Boolean(defaultAvailability?.is_available);
  const timeText = override
    ? override.is_available
      ? `${override.start_time}-${override.end_time}`
      : "Unavailable"
    : defaultAvailability?.is_available
      ? `${defaultAvailability.start_time}-${defaultAvailability.end_time}`
      : "Unavailable";

  return (
    <Pressable
      accessibilityRole="button"
      disabled={isPastDay}
      onPress={onPress}
      style={[
        styles.dayCell,
        isAvailable ? styles.dayCellAvailable : styles.dayCellUnavailable,
        override ? styles.dayCellOverride : null,
        isPastDay ? styles.dayCellPast : null,
      ]}
    >
      <Text style={[styles.dayNumber, isPastDay ? styles.dayTextPast : null]}>
        {day.dayNumber}
      </Text>
      <Text
        numberOfLines={1}
        style={[styles.dayTimeText, isPastDay ? styles.dayTextPast : null]}
      >
        {timeText}
      </Text>
    </Pressable>
  );
}

function syncDefaultForm(
  availabilities: ProviderAvailability[],
  setDefaultStartTime: (value: string) => void,
  setDefaultEndTime: (value: string) => void,
  setDefaultWeekdays: (value: number[]) => void,
) {
  const workingDays = availabilities.filter((item) => item.is_available);
  const firstWorkingDay = workingDays[0];

  if (firstWorkingDay) {
    setDefaultStartTime(firstWorkingDay.start_time);
    setDefaultEndTime(firstWorkingDay.end_time);
    setDefaultWeekdays(workingDays.map((item) => item.weekday).sort());
    return;
  }

  setDefaultWeekdays([]);
}

function getAvailabilityForWeekday(
  weekday: number,
  availabilities: ProviderAvailability[],
) {
  return availabilities.find((availability) => availability.weekday === weekday);
}

function getOverrideForDate(
  dateKey: string,
  overrides: ProviderAvailabilityOverride[],
) {
  return overrides.find((override) => override.override_date === dateKey);
}

function getWeekdayLabel(weekday: number) {
  return WEEKDAYS.find((item) => item.value === weekday)?.label ?? `Day ${weekday}`;
}

function getBookingsForDate(dateKey: string, bookings: BookingDetail[]) {
  return bookings.filter((booking) => bookingOverlapsDate(booking, dateKey));
}

function bookingOverlapsDate(booking: BookingDetail, dateKey: string) {
  const dayStart = new Date(`${dateKey}T00:00:00`);
  const dayEnd = new Date(`${dateKey}T23:59:59.999`);
  const bookingStart = new Date(booking.scheduled_start_time);
  const bookingEnd = new Date(booking.scheduled_end_time);

  return bookingStart < dayEnd && bookingEnd > dayStart;
}

function formatShortDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  return `${month}-${day} ${hour}:${minute}`;
}

function getBookingStatusLabel(status: string) {
  const labels: Record<string, string> = {
    accepted: "In progress",
    awaiting_confirmation: "Awaiting confirmation",
    visit_completed_closed: "Closed",
  };

  return labels[status] ?? status;
}

function parseDateKey(dateKey: string) {
  const [year, month, day] = dateKey.split("-").map(Number);

  return new Date(year, month - 1, day);
}

function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date: Date, amount: number) {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function compareMonths(left: Date, right: Date) {
  const leftMonth = left.getFullYear() * 12 + left.getMonth();
  const rightMonth = right.getFullYear() * 12 + right.getMonth();

  return leftMonth - rightMonth;
}

function formatMonthKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonthTitle(date: Date) {
  return `${date.getFullYear()} ${date.getMonth() + 1}`;
}

function formatDateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function getIsoWeekday(date: Date) {
  const day = date.getDay();
  return day === 0 ? 7 : day;
}

function buildCalendarDays(monthDate: Date): CalendarDay[] {
  const year = monthDate.getFullYear();
  const month = monthDate.getMonth();
  const firstDate = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const leadingEmptyDays = getIsoWeekday(firstDate) - 1;
  const days: CalendarDay[] = [];

  for (let index = 0; index < leadingEmptyDays; index += 1) {
    days.push({ dateKey: null, dayNumber: null });
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    days.push({
      dateKey: formatDateKey(new Date(year, month, day)),
      dayNumber: day,
    });
  }

  while (days.length % 7 !== 0) {
    days.push({ dateKey: null, dayNumber: null });
  }

  return days;
}

const styles = StyleSheet.create({
  content: {
    backgroundColor: colors.surface,
  },
  tabRow: {
    flexDirection: "row",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.xs,
  },
  segmentButton: {
    minHeight: 42,
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.sm,
  },
  segmentButtonActive: {
    backgroundColor: colors.primary,
  },
  segmentText: {
    color: colors.mutedText,
    fontSize: 15,
    fontWeight: "700",
  },
  segmentTextActive: {
    color: "#FFFFFF",
  },
  section: {
    gap: spacing.md,
  },
  defaultCard: {
    minHeight: 96,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  defaultIconBox: {
    width: 46,
    height: 46,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: "#E9F7F3",
  },
  defaultTextBox: {
    flex: 1,
    gap: spacing.xs,
  },
  cardTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "800",
  },
  cardText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 19,
  },
  linkText: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: "800",
  },
  calendarCard: {
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  calendarHeader: {
    minHeight: 42,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  monthButton: {
    width: 38,
    height: 38,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
  },
  monthButtonDisabled: {
    backgroundColor: colors.surface,
  },
  monthTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "800",
  },
  weekdayHeaderRow: {
    flexDirection: "row",
  },
  weekdayHeaderText: {
    width: `${100 / 7}%`,
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: "800",
    textAlign: "center",
  },
  loadingBox: {
    minHeight: 180,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
  },
  calendarGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  dayCell: {
    width: `${100 / 7}%`,
    minHeight: 74,
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: "transparent",
    borderRadius: radius.md,
    padding: spacing.xs,
  },
  dayCellAvailable: {
    borderColor: "#B7E4D5",
    backgroundColor: "#F0FBF7",
  },
  dayCellUnavailable: {
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  dayCellOverride: {
    borderColor: colors.primary,
  },
  dayCellPast: {
    borderColor: colors.border,
    backgroundColor: "#F4F4F5",
    opacity: 0.58,
  },
  jobDayCellActive: {
    borderColor: "#B7E4D5",
    backgroundColor: "#F0FBF7",
  },
  jobDayCellInactive: {
    borderColor: colors.border,
    backgroundColor: "#F4F4F5",
  },
  dayNumber: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800",
  },
  dayTimeText: {
    color: colors.mutedText,
    fontSize: 10,
  },
  dayTextPast: {
    color: "#A0A4AE",
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
  fieldLabel: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "700",
  },
  weekdayChipGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  weekdayChip: {
    minHeight: 38,
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.md,
  },
  weekdayChipSelected: {
    borderColor: colors.primary,
    backgroundColor: "#E9F7F3",
  },
  weekdayChipText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "700",
  },
  weekdayChipTextSelected: {
    color: colors.primary,
  },
  switchRow: {
    minHeight: 72,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  jobListContent: {
    gap: spacing.sm,
    paddingBottom: spacing.sm,
  },
  jobPreviewCard: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  jobPreviewHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  jobPreviewTitle: {
    flex: 1,
    color: colors.text,
    fontSize: 16,
    fontWeight: "800",
  },
  jobStatusBadge: {
    overflow: "hidden",
    borderRadius: 999,
    backgroundColor: "#E9F7F3",
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  descriptionFadeBox: {
    position: "relative",
    minHeight: 60,
    overflow: "hidden",
  },
  descriptionFade: {
    position: "absolute",
    right: 0,
    bottom: 0,
    width: 92,
    height: 20,
    backgroundColor: "rgba(255, 255, 255, 0.86)",
  },
  jobDescription: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
  },
  detailContent: {
    gap: spacing.sm,
    paddingBottom: spacing.sm,
  },
  detailRow: {
    gap: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingBottom: spacing.sm,
  },
  detailLabel: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: "800",
  },
  detailValue: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
  },
  modalActions: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  errorText: {
    color: colors.danger,
    fontSize: 13,
    lineHeight: 19,
  },
});
