import re
from typing import Optional


_KEYWORDS: dict[str, list[str]] = {
    "Groceries": [
        # English
        "milk", "bread", "cheese", "vegetable", "fruit", "apple", "banana",
        "egg", "chicken", "beef", "rice", "pasta", "supermarket", "grocery",
        "butter", "yogurt", "sugar", "flour", "oil", "juice", "coffee",
        "tea", "salt", "soap", "shampoo", "detergent", "meat", "fish",
        "tomato", "onion", "potato", "carrot", "lettuce", "cream", "cake",
        "biscuit", "cookie", "chocolate", "snack", "cereal", "noodle",
        "water", "drink", "beverage", "soda", "beer", "wine",
        # Bosnian / Serbian / Croatian (Latin)
        "mlijeko", "mleko", "kruh", "hljeb", "hleb", "sir", "jaje", "jaja",
        "piletina", "govedina", "riba", "riza", "tjestenina", "rezanci",
        "maslac", "jogurt", "secer", "brasno", "ulje", "sok", "kafa",
        "kava", "caj", "sol", "sapun", "sampon", "meso", "rajcica",
        "luk", "krumpir", "krompir", "mrkva", "zelena salata", "sladoled",
        "cokolada", "keks", "grickalice", "zitarice", "voda", "napitak",
        "namirnice", "prehrambeni", "prodavnica", "market", "pekara",
        "povrce", "voce", "jabuka", "narandza", "grejp",
        "lubenica", "kruska", "visnja", "tresnja", "malina",
        "jagoda", "borovnica", "orasi", "bademi", "kikiriki",
        "mineralna", "gazirana", "bezalkoholno", "pivo", "vino",
        "svjeze", "smrznuto", "konzerva", "tegla",
        # Bosnian / Serbian (Cyrillic)
        "млеко", "хлеб", "хљеб", "сир", "јаје", "јаја",
        "пилетина", "говедина", "риба", "пиринач", "тестенина",
        "путер", "јогурт", "шећер", "брашно", "уље", "сок", "кафа",
        "чај", "со", "сапун", "шампон", "месо", "парадајз",
        "лук", "кромпир", "шаргарепа", "вода", "напитак",
        "намирнице", "продавница", "пекара", "поврће", "воће",
        "јабука", "банана", "наранџа", "лубеница", "пиво", "вино",
        # Russian
        "молоко", "хлеб", "сыр", "яйцо", "яйца", "курица", "говядина",
        "рыба", "рис", "макароны", "масло", "сливочное", "йогурт",
        "сахар", "мука", "подсолнечное", "сок", "кофе", "чай",
        "соль", "мыло", "шампунь", "мясо", "помидор", "лук",
        "картофель", "морковь", "вода", "напиток", "продукты",
        "магазин", "супермаркет", "булочная", "хлебобулочные",
        "овощи", "фрукты", "яблоко", "банан", "апельсин",
        "шоколад", "печенье", "снэк", "крупа", "пиво", "вино",
    ],

    "Transportation": [
        # English
        "uber", "lyft", "taxi", "metro", "train", "bus", "ticket",
        "fuel", "gas", "petrol", "parking", "toll", "diesel", "highway",
        "subway", "tram", "ferry", "airline", "flight", "airport",
        "rental", "car wash", "carwash", "motor oil",
        # Bosnian / Serbian / Croatian (Latin)
        "gorivo", "benzin", "dizel", "nafta", "parking", "autobus",
        "voz", "vlak", "taksi", "prijevoz", "prevoz", "karta",
        "putarina", "tramvaj", "metro", "avion", "aerodrom",
        "autoprevoz", "taxi", "mazivo", "pranje auta", "servis",
        "registracija", "tehnicki", "tehničk",
        # Cyrillic
        "гориво", "бензин", "дизел", "нафта", "паркинг", "аутобус",
        "воз", "такси", "превоз", "карта", "путарина", "трамвај",
        "авион", "аеродром", "мазиво", "сервис",
        # Russian
        "бензин", "дизель", "топливо", "парковка", "автобус",
        "поезд", "такси", "трамвай", "метро", "авиа", "аэропорт",
        "проездной", "билет", "маршрутка", "электричка",
        "автомойка", "моторное масло",
    ],

    "Utilities": [
        # English
        "electric", "electricity", "water", "internet", "wifi",
        "utility", "power", "bill", "phone", "mobile", "heating",
        "gas", "sewage", "waste", "garbage", "telecom",
        # Bosnian / Serbian / Croatian (Latin)
        "struja", "voda", "internet", "telefon", "mobitel",
        "grijanje", "komunalije", "racun", "plin", "kanalizacija",
        "otpad", "smeće", "smece", "elektricna", "komunalna",
        "telekom", "bhtelecom", "m:tel", "vip", "telemach",
        # Cyrillic
        "струја", "вода", "интернет", "телефон", "мобилни",
        "грејање", "рачун", "комуналије", "канализација",
        # Russian
        "электричество", "вода", "интернет", "телефон",
        "отопление", "коммунальные", "газ", "канализация",
        "мусор", "счёт", "квитанция",
    ],

    "Entertainment": [
        # English
        "netflix", "spotify", "cinema", "movie", "game", "restaurant",
        "concert", "theater", "bar", "club", "hotel", "cafe", "coffee shop",
        "pub", "lounge", "gym", "fitness", "sport", "museum", "gallery",
        "bowling", "pizza", "burger", "sushi", "kebab", "fast food",
        "steam", "playstation", "xbox", "subscription",
        # Bosnian / Serbian / Croatian (Latin)
        "restoran", "kafic", "bioskop", "kino", "hotel", "zabava",
        "igra", "koncert", "pozoriste", "kafana", "bar", "pab",
        "teretana", "fitnes", "sport", "muzej", "galerija",
        "pizza", "burger", "kebab", "brza hrana", "picerija",
        "kafé", "kafe", "caffe", "slasticarna", "slatki",
        # Cyrillic
        "ресторан", "кафић", "биоскоп", "хотел", "забава",
        "игра", "концерт", "позориште", "кафана", "паб",
        "теретана", "фитнес", "музеј", "галерија",
        "пица", "бургер", "кебаб", "кафе",
        # Russian
        "ресторан", "кафе", "кино", "отель", "развлечения",
        "концерт", "театр", "бар", "клуб", "тренажерный",
        "фитнес", "музей", "галерея", "пицца", "бургер",
    ],

    "Healthcare": [
        # English
        "pharmacy", "medicine", "drug", "vitamin", "supplement",
        "bandage", "medical", "health", "dental", "doctor", "hospital",
        "clinic", "prescription", "tablet", "capsule", "syrup",
        "painkiller", "antibiotic", "cream", "ointment", "eyedrop",
        "contact lens", "glasses", "optical", "vaccine",
        # Common brand-name medicines (international)
        "aspirin", "ibuprofen", "paracetamol", "brufen", "andol", "nurofen",
        "voltaren", "lekadol", "analgin", "kaopectate", "loratadine",
        "cetirizine", "omeprazole", "pantoprazole", "metformin",
        "amoxicillin", "azithromycin", "doxycycline", "amoksicilin",
        # Bosnian / Serbian / Croatian (Latin)
        "apoteka", "lijek", "lijekovi", "lekovi", "vitamin", "tableta",
        "kapsula", "sirup", "zavoj", "flaster", "mast", "kapi",
        "medicinski", "zdravlje", "doktor", "bolnica", "klinika",
        "recept", "analgetik", "antibiotik", "dezinfekcija",
        "naocale", "kontaktne", "optika", "stomatoloski",
        # Cyrillic
        "апотека", "лијек", "лекови", "витамин", "таблета",
        "капсула", "сируп", "завој", "фластер", "маст", "капи",
        "медицински", "здравље", "доктор", "болница", "клиника",
        "рецепт", "аналгетик", "антибиотик", "дезинфекција",
        "наочале", "оптика",
        # Russian
        "аптека", "лекарство", "лекарства", "витамин", "таблетка",
        "капсула", "сироп", "бинт", "пластырь", "мазь", "капли",
        "медицинский", "здоровье", "доктор", "больница", "клиника",
        "рецепт", "антибиотик", "анальгетик", "дезинфекция",
        "очки", "оптика", "стоматолог",
    ],
}


def categorize_item(item_name: str, *, categories_by_name: dict[str, int]) -> tuple[Optional[int], float]:
    """
    Multilingual rule-based categorization.
    Supports English + Bosnian/Serbian/Croatian (Latin + Cyrillic) + Russian.
    Returns (category_id, confidence).
    """
    text = (item_name or "").lower()
    if not text.strip():
        return categories_by_name.get("Uncategorized"), 0.0

    # Exact word-boundary matches (highest confidence)
    for category_name, keywords in _KEYWORDS.items():
        for kw in keywords:
            if re.search(
                rf"(?<![a-zA-ZÀ-ɏЀ-ӿ]){re.escape(kw)}(?![a-zA-ZÀ-ɏЀ-ӿ])",
                text,
                flags=re.IGNORECASE | re.UNICODE,
            ):
                cid = categories_by_name.get(category_name)
                if cid is None:
                    continue
                return cid, 0.85

    # Substring containment fallback (lower confidence)
    for category_name, keywords in _KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                cid = categories_by_name.get(category_name)
                if cid is None:
                    continue
                return cid, 0.55

    return categories_by_name.get("Uncategorized"), 0.15
