AI_RECOMMENDATION_PROVIDER_TAGS = [
    "cleaning",
    "childcare",
    "elderly_care",
    "electrician",
    "plumbing",
    "painter",
    "locksmith",
    "technician",
    "moving",
]

ALLOWED_PROVIDER_TAGS = [
    *AI_RECOMMENDATION_PROVIDER_TAGS,
    "other",
]

DEMO_PASSWORD = "Demo1234"

# Public seeded identities; demo login never selects an arbitrary role member.
DEMO_USER_EMAILS = {
    "customer": "demo_customer_1@workshop.ai",
    "provider": "demo_provider_1@workshop.ai",
    "admin": "demo_admin@workshop.ai",
}
