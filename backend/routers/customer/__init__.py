from backend.utils.router import ApiRouter
from backend.routers.customer.bookings import router as bookings_router
from backend.routers.customer.discovery import router as discovery_router
from backend.routers.customer.feedback import router as feedback_router
from backend.routers.customer.profile import router as profile_router
from backend.routers.customer.address_book import router as address_book_router

router = ApiRouter(tags=["Customer"])
router.include_router(profile_router)
router.include_router(address_book_router)
router.include_router(discovery_router)
router.include_router(bookings_router)
router.include_router(feedback_router)
