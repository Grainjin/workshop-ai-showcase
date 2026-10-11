"""Field labels and follow-up questions for AI tool arguments."""

TOOL_FIELD_LABELS = {
    "provider_profile_id": "Provider",
    "provider_ids": "Provider",
    "booking_id": "Booking",
    "refund_request_id": "Refund request",
    "service_description": "Service description",
    "service_address": "Service address",
    "service_latitude": "Service latitude",
    "service_longitude": "Service longitude",
    "scheduled_start_time": "Start time",
    "scheduled_end_time": "End time",
    "reason": "Reason",
    "status_note": "Note",
    "provider_note": "Refund rejection reason",
    "quote_amount": "Quote amount",
    "question": "Question",
}


TOOL_FIELD_QUESTIONS = {
    "provider_profile_id": "Which provider would you like? Reply with a list number or provider id.",
    "provider_ids": "Please select one or more providers so I can summarize reviews.",
    "booking_id": "Which booking should I act on? Reply with booking id or a list number.",
    "refund_request_id": "Which refund request? Reply with id or a list number.",
    "service_description": "Describe the service needed, e.g. elderly daily care, escort, meal help, or other.",
    "service_address": "Please provide the service address.",
    "service_latitude": "Please provide service latitude; the app can fill this from location.",
    "service_longitude": "Please provide service longitude; the app can fill this from location.",
    "scheduled_start_time": "Please provide the start time.",
    "scheduled_end_time": "Please provide the end time.",
    "reason": "Please provide a reason.",
    "status_note": "Please provide a note.",
    "provider_note": "Please provide a reason for rejecting the refund.",
    "quote_amount": "Please provide a quote amount greater than 0.",
    "question": "Please provide your question.",
}

BOOKING_DRAFT_CONTINUATION_PROMPT = (
    "The user is completing an unfinished booking draft. "
    "Determine whether the message supplies missing or updated draft fields. "
    "If the user provides service description, address, coordinates, or start or end times, "
    "call prepare_booking_draft_action with only the new or changed fields from this turn. "
    "Do not call search_providers or re-recommend providers. "
    "If the user gives a time without a date and booking_draft.provided_fields.scheduled_start_time has a date, "
    "keep the draft date and update only the time. "
    "For coordinates like 44.22 32.11, the first number is service_latitude, the second service_longitude. "
    "Phrases like need lockout service or elderly daily care should become service_description. "
    "If no draft fields were provided, skip tools and explain what is still needed in the user's language."
)

BOOKING_DRAFT_CONTINUATION_KEYWORDS = [
    "address",
    "location",
    "latitude",
    "longitude",
    "coordinates",
    "time",
    "schedule",
    "appointment",
    "morning",
    "afternoon",
    "evening",
    "tonight",
    "tomorrow",
    "today",
    "need",
    "change",
    "update",
]


def get_tool_field_label(field_name: str):
    return TOOL_FIELD_LABELS.get(field_name, field_name)


def get_tool_field_question(field_name: str):
    return TOOL_FIELD_QUESTIONS.get(
        field_name,
        f"Please provide {get_tool_field_label(field_name)}.",
    )


def format_tool_missing_fields_answer(field_names: list[str]):
    unique_field_names = list(dict.fromkeys(field_names))

    if len(unique_field_names) == 1:
        return get_tool_field_question(unique_field_names[0])

    labels = [get_tool_field_label(field_name) for field_name in unique_field_names]
    answer_lines = [
        "I understand you want to continue, but I still need:"
        f"{', '.join(labels)}.",
        "Please provide:",
    ]
    answer_lines.extend(
        f"- {get_tool_field_question(field_name)}"
        for field_name in unique_field_names
    )

    return "\n".join(answer_lines)


def format_tool_invalid_fields_answer(field_names: list[str]):
    unique_field_names = list(dict.fromkeys(field_names))
    labels = [get_tool_field_label(field_name) for field_name in unique_field_names]

    answer_lines = [f"These fields have invalid format: {', '.join(labels)}."]
    answer_lines.extend(
        f"- {get_tool_field_question(field_name)}"
        for field_name in unique_field_names
    )

    return "\n".join(answer_lines)


