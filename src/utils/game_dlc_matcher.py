import re
import time
import unicodedata
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# Recognized multilingue Sims 4 prefixes
SIMS4_PREFIX_REGEX = re.compile(
    r"^(?:(?:the|les|die|los|i|gli|de|os)\s*)?sims(?:™|®)?\s*4\b|^ts4\b|^симс\s*4\b",
    re.IGNORECASE,
)

# Base game indicators to exclude from DLC categorization
BASE_GAME_REGEX = re.compile(
    r"^(?:(?:the|les|die|los|i|gli|de|os)\s*)?sims(?:™|®)?\s*4(?:\s*[:\-–—]?\s*(?:base\s*game|jeu\s*de\s*base|basisspiel|juego\s*base|gioco\s*base|\(?\s*(?:for|pour)?\s*(?:pc\s*(?:or|/|and|et|oder)\s*mac|pc|mac|windows|osx|linux)\s*\)?))?$|"
    r"^ts4(?:\s*[:\-–—]?\s*(?:base\s*game|jeu\s*de\s*base|basisspiel|\(?\s*(?:for|pour)?\s*(?:pc\s*(?:or|/|and|et|oder)\s*mac|pc|mac|windows|osx|linux)\s*\)?))?$|"
    r"^(?:base\s*game|jeu\s*de\s*base|basisspiel|juego\s*base|none|aucun|aucun[e]?|n/?a|-)$",
    re.IGNORECASE,
)

# Official Sims 4 Codes Mapping
OFFICIAL_SIMS4_CODES = {
    # Expansion Packs (EP)
    "EP01": "Get to Work / Au Travail",
    "EP02": "Get Together / Vivre Ensemble",
    "EP03": "City Living / Vie Citadine",
    "EP04": "Cats & Dogs / Chiens et Chats",
    "EP05": "Seasons / Saisons",
    "EP06": "Get Famous / Heure de Gloire",
    "EP07": "Island Living / Îles Paradisiaques",
    "EP08": "Discover University / À la Fac",
    "EP09": "Eco Lifestyle / Écologie",
    "EP10": "Snowy Escape / Escapade Enneigée",
    "EP11": "Cottage Living / Vie à la Campagne",
    "EP12": "High School Years / Années Lycée",
    "EP13": "Growing Together / Grandir Ensemble",
    "EP14": "Horse Ranch / Vie au Ranch",
    "EP15": "For Rent / À Louer",
    "EP16": "Lovestruck / Coup de Foudre",
    "EP17": "Life & Death / Vie et Mort",
    "EP18": "Businesses & Hobbies / Entreprises et Loisirs",
    "EP19": "Enchanted by Nature / Enchanté par la Nature",
    "EP20": "Adventure Awaits / L'Aventure Attend",
    "EP21": "Royalty & Legacy / Royauté et Héritage",
    # Game Packs (GP)
    "GP01": "Outdoor Retreat / Destination Nature",
    "GP02": "Spa Day / Détente au Spa",
    "GP03": "Dine Out / Au Resto",
    "GP04": "Vampires",
    "GP05": "Parenthood / Être Parents",
    "GP06": "Jungle Adventure / Dans la Jungle",
    "GP07": "StrangerVille",
    "GP08": "Realm of Magic / Monde Magique",
    "GP09": "Star Wars: Journey to Batuu / Voyage sur Batuu",
    "GP10": "Dream Home Decorator / Décoration d'Intérieur",
    "GP11": "My Wedding Stories / Mariage",
    "GP12": "Werewolves / Loups-Garous",
    # Stuff Packs (SP)
    "SP01": "Luxury Party / Soirée de Luxe",
    "SP02": "Perfect Patio / Ambiance Patio",
    "SP03": "Cool Kitchen / En Cuisine",
    "SP04": "Spooky / Accessoires Effrayants",
    "SP05": "Movie Hangout / Comme au Cinéma",
    "SP06": "Romantic Garden / Jardin Romantique",
    "SP07": "Kids Room / Chambre d'enfants",
    "SP08": "Backyard / En Plein Air",
    "SP09": "Vintage Glamour / Accessoires Vintage",
    "SP10": "Bowling Night / Soirée Bowling",
    "SP11": "Fitness",
    "SP12": "Toddler / Bambins",
    "SP13": "Laundry Day / Jour de Lessive",
    "SP14": "My First Pet / Premier Animal",
    "SP15": "Moschino",
    "SP16": "Tiny Living / Mini-Maisons",
    "SP17": "Nifty Knitting / Tricot de Pro",
    "SP18": "Paranormal",
    "SP19": "Home Chef Hustle / Passion Cuisine",
    "SP20": "Crystal Creations / Créations en Cristal",
    "SP46": "Home Chef Hustle / Passion Cuisine",
    "SP49": "Crystal Creations / Créations en Cristal",
    # Free Pack
    "FP01": "Holiday Celebration / Fêtes de Fin d'Année",
    # Kits (SP20+)
    "SP21": "Country Kitchen / Cuisine Rustique",
    "SP22": "Bust the Dust / Nettoyage de Printemps",
    "SP23": "Courtyard Oasis / Riad de Rêve",
    "SP24": "Fashion Street / Rue de la Mode",
    "SP25": "Industrial Loft / Loft Industriel",
    "SP26": "Incheon Arrivals / Arrivée à Incheon",
    "SP28": "Modern Menswear / Nouveaux Styles Masculins",
    "SP29": "Blooming Rooms / Intérieurs Fleuris",
    "SP30": "Carnaval Streetwear / Tenues de Carnaval",
    "SP31": "Decor to the Max / Déco Maximale",
    "SP32": "Moonlight Chic / Nuit Chic",
    "SP33": "Little Campers / Petits Campeurs",
    "SP34": "First Fits / Premiers Looks",
    "SP35": "Desert Luxe / Luxe dans le Désert",
    "SP36": "Pastel Pop",
    "SP37": "Everyday Clutter / Objets du Quotidien",
    "SP38": "Simtimates Collection / Collection Lingerie",
    "SP39": "Bathroom Clutter / Objets de Salle de Bain",
    "SP40": "Greenhouse Haven / Havre Végétal",
    "SP41": "Basement Treasures / Trésors du Grenier",
    "SP42": "Grunge Revival / Retour du Grunge",
    "SP43": "Book Nook / Coin Lecture",
    "SP44": "Poolside Splash / Plongeon au Bord de la Piscine",
    "SP45": "Modern Luxe / Luxe Moderne",
    "SP47": "Castle Estate / Châteaux de la Renaissance",
    "SP48": "Goth Galore / Style Gothique",
    "SP50": "Urban Homage / Hommage Urbain",
    "SP51": "Party Essentials / Fête Parfaite",
    "SP52": "Riviera Retreat / Destination Riviera",
    "SP53": "Cozy Bistro / Bistrot Charmant",
    "SP54": "Artist Studio / Atelier d'Artiste",
    "SP55": "Storybook Nursery / Chambre d'Enfant Féerique",
    "SP56": "Sweet Slumber Party / Pyjama Party",
    "SP57": "Cozy Kitsch / Rétro Kitsch",
    "SP58": "Comfy Gamer",
    "SP59": "Secret Sanctuary",
    "SP60": "Casanova Cave",
    "SP61": "Refined Living Room",
    "SP62": "Business Chic",
    "SP63": "Sleek Bathroom",
    "SP64": "Sweet Allure",
    "SP65": "Restoration Workshop",
    "SP66": "Golden Years",
    "SP67": "Kitchen Clutter",
    "SP68": "SpongeBob's House",
    "SP69": "Autumn Apparel",
    "SP70": "SpongeBob Kid's Room",
    "SP71": "Grange Mudroom",
    "SP72": "Essential Glam",
    "SP73": "Modern Retreat",
    "SP74": "Garden to Table",
    "SP75": "Wonderland Playroom",
    "SP76": "Silver Screen Style",
    "SP77": "Tea Time Solarium",
    "SP78": "Lady Bridgerton's Masquerade Ball Fashion",
    "SP79": "Lady Bridgerton's Masquerade Ballroom",
    "SP80": "Music Den",
    "SP81": "Prairie Dreams",
    "SP82": "Yard Charm",
    "SP83": "Mean Girls Capsule",
    "SP84": "Clueless Capsule",
    "SP87": "Coach RePurposed Capsule",
}

# Exhaustive known DLC / Pack nicknames and codes (Bilingual EN / FR / Aliases)
KNOWN_DLC_NAMES = {
    # Expansion Packs (EP)
    "get to work": ("EP01", "Get to Work / Au Travail"),
    "au travail": ("EP01", "Get to Work / Au Travail"),
    "an die arbeit": ("EP01", "Get to Work / Au Travail"),
    "get together": ("EP02", "Get Together / Vivre Ensemble"),
    "vivre ensemble": ("EP02", "Get Together / Vivre Ensemble"),
    "city living": ("EP03", "City Living / Vie Citadine"),
    "vie citadine": ("EP03", "City Living / Vie Citadine"),
    "cats & dogs": ("EP04", "Cats & Dogs / Chiens et Chats"),
    "cats and dogs": ("EP04", "Cats & Dogs / Chiens et Chats"),
    "chiens et chats": ("EP04", "Cats & Dogs / Chiens et Chats"),
    "seasons": ("EP05", "Seasons / Saisons"),
    "saisons": ("EP05", "Seasons / Saisons"),
    "jahreszeiten": ("EP05", "Seasons / Saisons"),
    "get famous": ("EP06", "Get Famous / Heure de Gloire"),
    "heure de gloire": ("EP06", "Get Famous / Heure de Gloire"),
    "island living": ("EP07", "Island Living / Îles Paradisiaques"),
    "iles paradisiaques": ("EP07", "Island Living / Îles Paradisiaques"),
    "discover university": ("EP08", "Discover University / À la Fac"),
    "a la fac": ("EP08", "Discover University / À la Fac"),
    "eco lifestyle": ("EP09", "Eco Lifestyle / Écologie"),
    "ecologie": ("EP09", "Eco Lifestyle / Écologie"),
    "snowy escape": ("EP10", "Snowy Escape / Escapade Enneigée"),
    "escapade enneigee": ("EP10", "Snowy Escape / Escapade Enneigée"),
    "cottage living": ("EP11", "Cottage Living / Vie à la Campagne"),
    "vie a la campagne": ("EP11", "Cottage Living / Vie à la Campagne"),
    "high school years": ("EP12", "High School Years / Années Lycée"),
    "annees lycee": ("EP12", "High School Years / Années Lycée"),
    "growing together": ("EP13", "Growing Together / Grandir Ensemble"),
    "grandir ensemble": ("EP13", "Growing Together / Grandir Ensemble"),
    "horse ranch": ("EP14", "Horse Ranch / Vie au Ranch"),
    "vie au ranch": ("EP14", "Horse Ranch / Vie au Ranch"),
    "for rent": ("EP15", "For Rent / À Louer"),
    "a louer": ("EP15", "For Rent / À Louer"),
    "lovestruck": ("EP16", "Lovestruck / Coup de Foudre"),
    "coup de foudre": ("EP16", "Lovestruck / Coup de Foudre"),
    "life & death": ("EP17", "Life & Death / Vie et Mort"),
    "life and death": ("EP17", "Life & Death / Vie et Mort"),
    "vie et mort": ("EP17", "Life & Death / Vie et Mort"),
    "businesses & hobbies": ("EP18", "Businesses & Hobbies / Entreprises et Loisirs"),
    "businesses and hobbies": ("EP18", "Businesses & Hobbies / Entreprises et Loisirs"),
    "entreprises et loisirs": ("EP18", "Businesses & Hobbies / Entreprises et Loisirs"),
    "enchanted by nature": ("EP19", "Enchanted by Nature / Enchanté par la Nature"),
    "enchante par la nature": ("EP19", "Enchanted by Nature / Enchanté par la Nature"),
    "adventure awaits": ("EP20", "Adventure Awaits / L'Aventure Attend"),
    "aventure attend": ("EP20", "Adventure Awaits / L'Aventure Attend"),
    "royalty & legacy": ("EP21", "Royalty & Legacy / Royauté et Héritage"),
    "royalty and legacy": ("EP21", "Royalty & Legacy / Royauté et Héritage"),
    "royaute et heritage": ("EP21", "Royalty & Legacy / Royauté et Héritage"),
    # Game Packs (GP)
    "outdoor retreat": ("GP01", "Outdoor Retreat / Destination Nature"),
    "destination nature": ("GP01", "Outdoor Retreat / Destination Nature"),
    "spa day": ("GP02", "Spa Day / Détente au Spa"),
    "detente au spa": ("GP02", "Spa Day / Détente au Spa"),
    "dine out": ("GP03", "Dine Out / Au Resto"),
    "au resto": ("GP03", "Dine Out / Au Resto"),
    "vampires": ("GP04", "Vampires"),
    "parenthood": ("GP05", "Parenthood / Être Parents"),
    "etre parents": ("GP05", "Parenthood / Être Parents"),
    "jungle adventure": ("GP06", "Jungle Adventure / Dans la Jungle"),
    "dans la jungle": ("GP06", "Jungle Adventure / Dans la Jungle"),
    "strangerville": ("GP07", "StrangerVille"),
    "realm of magic": ("GP08", "Realm of Magic / Monde Magique"),
    "monde magique": ("GP08", "Realm of Magic / Monde Magique"),
    "journey to batuu": ("GP09", "Star Wars: Journey to Batuu / Voyage sur Batuu"),
    "star wars journey to batuu": ("GP09", "Star Wars: Journey to Batuu / Voyage sur Batuu"),
    "voyage sur batuu": ("GP09", "Star Wars: Journey to Batuu / Voyage sur Batuu"),
    "dream home decorator": ("GP10", "Dream Home Decorator / Décoration d'Intérieur"),
    "decoration d interieur": ("GP10", "Dream Home Decorator / Décoration d'Intérieur"),
    "my wedding stories": ("GP11", "My Wedding Stories / Mariage"),
    "histoires de mariage": ("GP11", "My Wedding Stories / Mariage"),
    "werewolves": ("GP12", "Werewolves / Loups-Garous"),
    "loups garous": ("GP12", "Werewolves / Loups-Garous"),
    # Stuff Packs (SP)
    "luxury party": ("SP01", "Luxury Party / Soirée de Luxe"),
    "soiree de luxe": ("SP01", "Luxury Party / Soirée de Luxe"),
    "perfect patio": ("SP02", "Perfect Patio / Ambiance Patio"),
    "ambiance patio": ("SP02", "Perfect Patio / Ambiance Patio"),
    "cool kitchen": ("SP03", "Cool Kitchen / En Cuisine"),
    "en cuisine": ("SP03", "Cool Kitchen / En Cuisine"),
    "spooky": ("SP04", "Spooky / Accessoires Effrayants"),
    "spooky stuff": ("SP04", "Spooky / Accessoires Effrayants"),
    "accessoires effrayants": ("SP04", "Spooky / Accessoires Effrayants"),
    "movie hangout": ("SP05", "Movie Hangout / Comme au Cinéma"),
    "comme au cinema": ("SP05", "Movie Hangout / Comme au Cinéma"),
    "romantic garden": ("SP06", "Romantic Garden / Jardin Romantique"),
    "jardin romantique": ("SP06", "Romantic Garden / Jardin Romantique"),
    "kids room": ("SP07", "Kids Room / Chambre d'enfants"),
    "chambre d enfants": ("SP07", "Kids Room / Chambre d'enfants"),
    "backyard": ("SP08", "Backyard / En Plein Air"),
    "en plein air": ("SP08", "Backyard / En Plein Air"),
    "vintage glamour": ("SP09", "Vintage Glamour / Accessoires Vintage"),
    "accessoires vintage": ("SP09", "Vintage Glamour / Accessoires Vintage"),
    "bowling night": ("SP10", "Bowling Night / Soirée Bowling"),
    "soiree bowling": ("SP10", "Bowling Night / Soirée Bowling"),
    "fitness": ("SP11", "Fitness"),
    "fitness stuff": ("SP11", "Fitness"),
    "toddler": ("SP12", "Toddler / Bambins"),
    "bambins": ("SP12", "Toddler / Bambins"),
    "laundry day": ("SP13", "Laundry Day / Jour de Lessive"),
    "jour de lessive": ("SP13", "Laundry Day / Jour de Lessive"),
    "my first pet": ("SP14", "My First Pet / Premier Animal"),
    "premier animal": ("SP14", "My First Pet / Premier Animal"),
    "moschino": ("SP15", "Moschino"),
    "moshino": ("SP15", "Moschino"),
    "tiny living": ("SP16", "Tiny Living / Mini-Maisons"),
    "mini maisons": ("SP16", "Tiny Living / Mini-Maisons"),
    "nifty knitting": ("SP17", "Nifty Knitting / Tricot de Pro"),
    "tricot de pro": ("SP17", "Nifty Knitting / Tricot de Pro"),
    "paranormal": ("SP18", "Paranormal"),
    "home chef hustle": ("SP19", "Home Chef Hustle / Passion Cuisine"),
    "passion cuisine": ("SP19", "Home Chef Hustle / Passion Cuisine"),
    "crystal creations": ("SP20", "Crystal Creations / Créations en Cristal"),
    "creations en cristal": ("SP20", "Crystal Creations / Créations en Cristal"),
    # Kits & Creator Kits (SP20+)
    "throwback fit": ("SP20", "Throwback Fit / Look Rétro"),
    "look retro": ("SP20", "Throwback Fit / Look Rétro"),
    "country kitchen": ("SP21", "Country Kitchen / Cuisine Rustique"),
    "cuisine rustique": ("SP21", "Country Kitchen / Cuisine Rustique"),
    "bust the dust": ("SP22", "Bust the Dust / Nettoyage de Printemps"),
    "nettoyage de printemps": ("SP22", "Bust the Dust / Nettoyage de Printemps"),
    "courtyard oasis": ("SP23", "Courtyard Oasis / Riad de Rêve"),
    "riad de reve": ("SP23", "Courtyard Oasis / Riad de Rêve"),
    "fashion street": ("SP24", "Fashion Street / Rue de la Mode"),
    "rue de la mode": ("SP24", "Fashion Street / Rue de la Mode"),
    "industrial loft": ("SP25", "Industrial Loft / Loft Industriel"),
    "loft industriel": ("SP25", "Industrial Loft / Loft Industriel"),
    "incheon arrivals": ("SP26", "Incheon Arrivals / Arrivée à Incheon"),
    "arrivee a incheon": ("SP26", "Incheon Arrivals / Arrivée à Incheon"),
    "modern menswear": ("SP28", "Modern Menswear / Nouveaux Styles Masculins"),
    "nouveaux styles masculins": ("SP28", "Modern Menswear / Nouveaux Styles Masculins"),
    "blooming rooms": ("SP29", "Blooming Rooms / Intérieurs Fleuris"),
    "interieurs fleuris": ("SP29", "Blooming Rooms / Intérieurs Fleuris"),
    "carnaval streetwear": ("SP30", "Carnaval Streetwear / Tenues de Carnaval"),
    "tenues de carnaval": ("SP30", "Carnaval Streetwear / Tenues de Carnaval"),
    "decor to the max": ("SP31", "Decor to the Max / Déco Maximale"),
    "deco maximale": ("SP31", "Decor to the Max / Déco Maximale"),
    "moonlight chic": ("SP32", "Moonlight Chic / Nuit Chic"),
    "nuit chic": ("SP32", "Moonlight Chic / Nuit Chic"),
    "little campers": ("SP33", "Little Campers / Petits Campeurs"),
    "petits campeurs": ("SP33", "Little Campers / Petits Campeurs"),
    "first fits": ("SP34", "First Fits / Premiers Looks"),
    "premiers looks": ("SP34", "First Fits / Premiers Looks"),
    "desert luxe": ("SP35", "Desert Luxe / Luxe dans le Désert"),
    "luxe dans le desert": ("SP35", "Desert Luxe / Luxe dans le Désert"),
    "pastel pop": ("SP36", "Pastel Pop"),
    "everyday clutter": ("SP37", "Everyday Clutter / Objets du Quotidien"),
    "objets du quotidien": ("SP37", "Everyday Clutter / Objets du Quotidien"),
    "simtimates collection": ("SP38", "Simtimates Collection / Collection Lingerie"),
    "collection lingerie": ("SP38", "Simtimates Collection / Collection Lingerie"),
    "bathroom clutter": ("SP39", "Bathroom Clutter / Objets de Salle de Bain"),
    "objets de salle de bain": ("SP39", "Bathroom Clutter / Objets de Salle de Bain"),
    "greenhouse haven": ("SP40", "Greenhouse Haven / Havre Végétal"),
    "havre vegetal": ("SP40", "Greenhouse Haven / Havre Végétal"),
    "basement treasures": ("SP41", "Basement Treasures / Trésors du Grenier"),
    "tresors du grenier": ("SP41", "Basement Treasures / Trésors du Grenier"),
    "grunge revival": ("SP42", "Grunge Revival / Retour du Grunge"),
    "retour du grunge": ("SP42", "Grunge Revival / Retour du Grunge"),
    "book nook": ("SP43", "Book Nook / Coin Lecture"),
    "coin lecture": ("SP43", "Book Nook / Coin Lecture"),
    "poolside splash": ("SP44", "Poolside Splash / Plongeon au Bord de la Piscine"),
    "plongeon au bord de la piscine": ("SP44", "Poolside Splash / Plongeon au Bord de la Piscine"),
    "modern luxe": ("SP45", "Modern Luxe / Luxe Moderne"),
    "luxe moderne": ("SP45", "Modern Luxe / Luxe Moderne"),
    "castle estate": ("SP47", "Castle Estate / Châteaux de la Renaissance"),
    "chateaux de la renaissance": ("SP47", "Castle Estate / Châteaux de la Renaissance"),
    "goth galore": ("SP48", "Goth Galore / Style Gothique"),
    "style gothique": ("SP48", "Goth Galore / Style Gothique"),
    "urban homage": ("SP50", "Urban Homage / Hommage Urbain"),
    "hommage urbain": ("SP50", "Urban Homage / Hommage Urbain"),
    "party essentials": ("SP51", "Party Essentials / Fête Parfaite"),
    "fete parfaite": ("SP51", "Party Essentials / Fête Parfaite"),
    "riviera retreat": ("SP52", "Riviera Retreat / Destination Riviera"),
    "destination riviera": ("SP52", "Riviera Retreat / Destination Riviera"),
    "cozy bistro": ("SP53", "Cozy Bistro / Bistrot Charmant"),
    "bistrot charmant": ("SP53", "Cozy Bistro / Bistrot Charmant"),
    "artist studio": ("SP54", "Artist Studio / Atelier d'Artiste"),
    "atelier d artiste": ("SP54", "Artist Studio / Atelier d'Artiste"),
    "storybook nursery": ("SP55", "Storybook Nursery / Chambre d'Enfant Féerique"),
    "chambre d enfant feerique": ("SP55", "Storybook Nursery / Chambre d'Enfant Féerique"),
    "sweet slumber party": ("SP56", "Sweet Slumber Party / Pyjama Party"),
    "pyjama party": ("SP56", "Sweet Slumber Party / Pyjama Party"),
    "cozy kitsch": ("SP57", "Cozy Kitsch / Rétro Kitsch"),
    "retro kitsch": ("SP57", "Cozy Kitsch / Rétro Kitsch"),
    "comfy gamer": ("SP58", "Comfy Gamer"),
    "secret sanctuary": ("SP59", "Secret Sanctuary"),
    "casanova cave": ("SP60", "Casanova Cave"),
    "refined living room": ("SP61", "Refined Living Room"),
    "business chic": ("SP62", "Business Chic"),
    "sleek bathroom": ("SP63", "Sleek Bathroom"),
    "sweet allure": ("SP64", "Sweet Allure"),
    "restoration workshop": ("SP65", "Restoration Workshop"),
    "golden years": ("SP66", "Golden Years"),
    "kitchen clutter": ("SP67", "Kitchen Clutter"),
    "spongebob s house": ("SP68", "SpongeBob's House"),
    "spongebobs house": ("SP68", "SpongeBob's House"),
    "autumn apparel": ("SP69", "Autumn Apparel"),
    "spongebob kids room": ("SP70", "SpongeBob Kid's Room"),
    "grange mudroom": ("SP71", "Grange Mudroom"),
    "essential glam": ("SP72", "Essential Glam"),
    "modern retreat": ("SP73", "Modern Retreat"),
    "garden to table": ("SP74", "Garden to Table"),
    "wonderland playroom": ("SP75", "Wonderland Playroom"),
    "silver screen style": ("SP76", "Silver Screen Style"),
    "tea time solarium": ("SP77", "Tea Time Solarium"),
    "lady bridgertons masquerade ball fashion": ("SP78", "Lady Bridgerton's Masquerade Ball Fashion"),
    "lady bridgertons masquerade ballroom": ("SP79", "Lady Bridgerton's Masquerade Ballroom"),
    "music den": ("SP80", "Music Den"),
    "prairie dreams": ("SP81", "Prairie Dreams"),
    "yard charm": ("SP82", "Yard Charm"),
    "mean girls capsule": ("SP83", "Mean Girls Capsule"),
    "clueless capsule": ("SP84", "Clueless Capsule"),
    "coach repurposed capsule": ("SP87", "Coach RePurposed Capsule"),
    # Free Packs
    "holiday celebration": ("FP01", "Holiday Celebration / Fêtes de Fin d'Année"),
    "fetes de fin d annee": ("FP01", "Holiday Celebration / Fêtes de Fin d'Année"),
}


class GameDlcMatcher:
    """
    Identifies if a mod dependency represents an official The Sims 4 DLC / Game Pack
    in multiple languages from a fixed official list, rather than a downloadable user mod.
    NO HEURISTIC GUESSING: only official DLCs are recognized; all other items are user mods.
    """

    _FP_MAP: Dict[str, Tuple[str, Tuple[str, str]]] = {}
    _SORTED_FP_ITEMS: List[Tuple[str, Tuple[str, Tuple[str, str]]]] = []
    _dlc_installed_cache: Dict[Tuple[str, str], Tuple[float, Optional[bool]]] = {}
    _CACHE_TTL_SECONDS: float = 60.0

    @classmethod
    def _ensure_fp_index(cls) -> None:
        """Initialise une seule fois l'index pré-calculé des empreintes de DLC."""
        if not cls._FP_MAP:
            cls._FP_MAP = {cls.canonical_fingerprint(k): (k, v) for k, v in KNOWN_DLC_NAMES.items()}
            cls._SORTED_FP_ITEMS = sorted(cls._FP_MAP.items(), key=lambda item: len(item[0]), reverse=True)

    @classmethod
    def clear_cache(cls) -> None:
        """Vide le cache mémoire de détection d'installation des DLC."""
        cls._dlc_installed_cache.clear()

    @classmethod
    def is_base_game_only(cls, text: str) -> bool:
        """Returns True if the text only refers to the Sims 4 base game without any pack."""
        if not text:
            return False
        clean = text.strip().strip("'\"`[](){}").rstrip(".,;:-")
        if BASE_GAME_REGEX.fullmatch(clean):
            return True
        m = SIMS4_PREFIX_REGEX.match(clean)
        if m:
            rest = clean[m.end() :].strip(" :\\-–—.,;()[]")
            if not rest or re.fullmatch(
                r"(?i)(?:base\s*game|jeu\s*de\s*base|basisspiel|juego\s*base|gioco\s*base|(?:for|pour)?\s*(?:pc\s*(?:or|/|and|et|oder)\s*mac|pc|mac|windows|osx|linux).*)",
                rest,
            ):
                return True
        return False

    @classmethod
    def canonical_fingerprint(cls, text: str) -> str:
        """Generates an alphanumeric fingerprint without spaces, hyphens, or accents."""
        if not text:
            return ""
        name = unicodedata.normalize("NFKD", text)
        name = "".join(c for c in name if not unicodedata.combining(c))
        name = name.replace("&", "and")
        return re.sub(r"[^a-zA-Z0-9]", "", name).lower()

    @classmethod
    def match_dlc(cls, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Analyzes a dependency string against the official fixed DLC catalog.
        Returns:
            (is_dlc, pack_name, pack_code)
            - is_dlc: bool
            - pack_name: clean display name of the DLC (e.g., 'City Living / Vie Citadine')
            - pack_code: EP/GP/SP/FP code if recognized (e.g., 'EP03'), else None
        """
        if not text:
            return False, None, None

        # Clean leading bullets, dashes, brackets, colons
        clean = re.sub(r"^[\s•\*\-\–\—\d\.\)\:\[\]\(\)\{\}\"\'\`]+", "", text).strip()
        # Clean leading requirement prefixes (e.g. "Requires:", "Requirements:", "Need:", "DLC:", "Pack:")
        clean = (
            re.sub(
                r"(?i)^(?:requirements?|pr[ée]requis|prerequisites?|needs?|required(?:\s*(?:mods?|packs?|dlcs?))?|requires?|dlcs?|packs?)\s*[:\-–—\s]\s*",
                "",
                clean,
            )
            .strip()
            .strip("'\"`[](){}")
        )

        if not clean or cls.is_base_game_only(clean):
            return False, None, None

        # 1. Check explicit pack code regex (e.g. EP01, EP1, GP05, SP13, FP01)
        m_code = re.search(r"\b(EP|GP|SP|FP)[\s\-_]?(\d{1,2})\b", clean, re.IGNORECASE)
        if m_code:
            prefix = m_code.group(1).upper()
            num = int(m_code.group(2))
            pack_code = f"{prefix}{num:02d}"
            if pack_code in OFFICIAL_SIMS4_CODES:
                return True, OFFICIAL_SIMS4_CODES[pack_code], pack_code

        # Strip optional localized Sims 4 prefix if present
        m_prefix = SIMS4_PREFIX_REGEX.match(clean)
        content_after_prefix = clean
        if m_prefix:
            content_after_prefix = clean[m_prefix.end() :].strip(" :\\-–—.,;()[]{}")

        # Clean content of generic pack descriptors for clean lookup
        clean_name = re.sub(
            r"(?i)\s*\b(?:expansion\s*pack|game\s*pack|stuff\s*pack|kit\s*d['’]objets|pack\s*d['’]extension|pack\s*de\s*jeu|mini-?kit|creator\s*kit|capsule\s*kit|kits?|dlc|packs?)\b\s*",
            " ",
            content_after_prefix,
        ).strip(": -–—()[]{}")
        if not clean_name:
            clean_name = content_after_prefix

        normalized_key = cls._normalize_lookup_key(clean_name)
        cand_fp = cls.canonical_fingerprint(clean_name)
        full_cand_fp = cls.canonical_fingerprint(clean)

        cls._ensure_fp_index()

        # 2. Exact match in official dictionary
        if normalized_key in KNOWN_DLC_NAMES:
            code, std_name = KNOWN_DLC_NAMES[normalized_key]
            return True, std_name, code
        if cand_fp in cls._FP_MAP:
            _k, (code, std_name) = cls._FP_MAP[cand_fp]
            return True, std_name, code

        # 3. Substring matching against official DLC entries
        # Tolerate partial matching only if an official DLC name from the fixed catalog is detected
        # Order by key length descending to match most specific pack first
        for k_fp, (orig_key, (code, std_name)) in cls._SORTED_FP_ITEMS:
            if len(k_fp) < 4:
                continue

            # Check if key is a distinct word in clean text, or canonical fingerprint substring
            if len(k_fp) >= 5 and (k_fp in cand_fp or k_fp in full_cand_fp):
                norm_clean = f" {cls._normalize_lookup_key(clean)} "
                if f" {orig_key} " in norm_clean or k_fp in cand_fp:
                    return True, std_name, code

        # Strict: NO HEURISTIC GUESSING!
        # If not found in fixed catalog, it is NOT an official DLC.
        return False, None, None

    @classmethod
    def _normalize_lookup_key(cls, name: str) -> str:
        """Normalizes accents, punctuation, and multiple spaces for dictionary matching."""
        name = unicodedata.normalize("NFKD", name)
        name = "".join(c for c in name if not unicodedata.combining(c))
        name = name.replace("&", "and").replace("'", "").replace("’", "")
        name = re.sub(r"[^a-zA-Z0-9\s]", " ", name)
        return re.sub(r"\s+", " ", name).strip().lower()

    @classmethod
    def is_dlc_installed_in_game(cls, pack_code: Optional[str], game_dir: Optional[Path] = None) -> Optional[bool]:
        """
        Checks if the pack (e.g., 'EP01', 'GP05') folder exists in the game installation directory.
        Returns True if detected, False if directory was found but pack folder is missing,
        or None if game directory is unknown.
        """
        if not pack_code:
            return None

        try:
            code_upper = pack_code.upper()
            if game_dir is not None:
                root_key = str(game_dir)
                potential_roots = [game_dir]
            else:
                from src.application.game.game_service import GameService

                game_exe = GameService.get_game_exe_path()
                if not game_exe or not game_exe.exists():
                    return None
                root_key = str(game_exe)
                potential_roots = [
                    game_exe.parent,
                    game_exe.parent.parent,
                    game_exe.parent.parent.parent,
                ]

            cache_key = (code_upper, root_key)
            now = time.monotonic()
            cached = cls._dlc_installed_cache.get(cache_key)
            if cached is not None and (now - cached[0]) < cls._CACHE_TTL_SECONDS:
                return cached[1]

            result: Optional[bool] = False
            for root in potential_roots:
                if root.exists():
                    if (root / code_upper).is_dir() or (root / "Delta" / code_upper).is_dir():
                        result = True
                        break

            cls._dlc_installed_cache[cache_key] = (now, result)
            return result
        except Exception:
            return None
