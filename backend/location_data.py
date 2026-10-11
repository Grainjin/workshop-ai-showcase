"""Deterministic service-area seed data for Turkey."""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class LocationSeed:
    code: str
    name: str
    level: str
    parent_code: str | None = None


TURKEY_PROVINCES = (
    "Adana", "Adiyaman", "Afyonkarahisar", "Agri", "Aksaray", "Amasya",
    "Ankara", "Antalya", "Ardahan", "Artvin", "Aydin", "Balikesir",
    "Bartin", "Batman", "Bayburt", "Bilecik", "Bingol", "Bitlis",
    "Bolu", "Burdur", "Bursa", "Canakkale", "Cankiri", "Corum",
    "Denizli", "Diyarbakir", "Duzce", "Edirne", "Elazig", "Erzincan",
    "Erzurum", "Eskisehir", "Gaziantep", "Giresun", "Gumushane", "Hakkari",
    "Hatay", "Igdir", "Isparta", "Istanbul", "Izmir", "Kahramanmaras",
    "Karabuk", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kilis",
    "Kirikkale", "Kirklareli", "Kirsehir", "Kocaeli", "Konya", "Kutahya",
    "Malatya", "Manisa", "Mardin", "Mersin", "Mugla", "Mus", "Nevsehir",
    "Nigde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Sanliurfa",
    "Siirt", "Sinop", "Sirnak", "Sivas", "Tekirdag", "Tokat", "Trabzon",
    "Tunceli", "Usak", "Van", "Yalova", "Yozgat", "Zonguldak",
)


SPECIAL_DISTRICTS = {
    "Istanbul": (
        "Adalar", "Atasehir", "Avcilar", "Bakirkoy", "Basaksehir", "Besiktas",
        "Beykoz", "Beylikduzu", "Beyoglu", "Buyukcekmece", "Kadikoy", "Kartal",
        "Kucukcekmece", "Maltepe", "Pendik", "Sariyer", "Silivri", "Sisli",
        "Sultanbeyli", "Tuzla", "Umraniye", "Uskudar",
    ),
    "Ankara": (
        "Akyurt", "Altindag", "Beypazari", "Cankaya", "Cubuk", "Etimesgut",
        "Golbasi", "Kecioren", "Mamak", "Polatli", "Pursaklar", "Sincan",
        "Yenimahalle",
    ),
    "Izmir": (
        "Aliaga", "Balcova", "Bayrakli", "Bergama", "Bornova", "Buca", "Cesme",
        "Cigli", "Foca", "Gaziemir", "Karabaglar", "Karaburun", "Karsiyaka",
        "Konak", "Menderes", "Menemen", "Narlidere", "Odemis", "Seferihisar",
        "Selcuk", "Tire", "Torbali", "Urla",
    ),
}


def _code(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def iter_location_seeds():
    for province in TURKEY_PROVINCES:
        province_code = f"tr-{_code(province)}"
        city_code = f"{province_code}-city"
        yield LocationSeed(province_code, province, "province")
        yield LocationSeed(city_code, province, "city", province_code)
        districts = SPECIAL_DISTRICTS.get(province, (f"{province} Merkez",))
        for district in districts:
            yield LocationSeed(
                f"{city_code}-{_code(district)}",
                district,
                "district",
                city_code,
            )
