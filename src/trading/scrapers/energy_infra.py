"""
Energy infrastructure geodata: mines, pipelines, LNG terminals, shipping lanes.

Static data module — no API calls. Provides location and metadata for
major mining operations, energy pipelines, LNG import/export terminals,
and critical shipping lanes used in the geointel map overlay.
"""

MINES: list[dict] = [
    {"name": "Grasberg", "lat": -4.05, "lon": 137.11, "type": "copper/gold", "commodity": "copper", "country": "Indonesia", "production": "massive"},
    {"name": "Muruntau", "lat": 41.55, "lon": 64.57, "type": "gold", "commodity": "gold", "country": "Uzbekistan", "production": "massive"},
    {"name": "Olympic Dam", "lat": -30.45, "lon": 136.88, "type": "copper/gold/uranium", "commodity": "copper", "country": "Australia", "production": "large"},
    {"name": "Escondida", "lat": -24.27, "lon": -69.07, "type": "copper", "commodity": "copper", "country": "Chile", "production": "massive"},
    {"name": "Chuquicamata", "lat": -22.32, "lon": -68.93, "type": "copper", "commodity": "copper", "country": "Chile", "production": "large"},
    {"name": "Norilsk", "lat": 69.35, "lon": 88.20, "type": "nickel/copper", "commodity": "copper", "country": "Russia", "production": "large"},
    {"name": "Bushveld Complex", "lat": -24.68, "lon": 29.45, "type": "platinum", "commodity": "rare_earth", "country": "South Africa", "production": "massive"},
    {"name": "Palabora", "lat": -23.98, "lon": 31.13, "type": "copper", "commodity": "copper", "country": "South Africa", "production": "medium"},
    {"name": "Bingham Canyon", "lat": 40.53, "lon": -112.15, "type": "copper", "commodity": "copper", "country": "USA", "production": "large"},
    {"name": "Cobre Panama", "lat": 8.83, "lon": -80.65, "type": "copper", "commodity": "copper", "country": "Panama", "production": "large"},
    {"name": "Carlin Trend", "lat": 40.73, "lon": -116.12, "type": "gold", "commodity": "gold", "country": "USA", "production": "massive"},
    {"name": "Kibali", "lat": 3.54, "lon": 29.60, "type": "gold", "commodity": "gold", "country": "DRC", "production": "large"},
    {"name": "Pueblo Viejo", "lat": 19.11, "lon": -70.03, "type": "gold", "commodity": "gold", "country": "Dominican Republic", "production": "large"},
    {"name": "Boddington", "lat": -32.75, "lon": 116.38, "type": "gold/copper", "commodity": "gold", "country": "Australia", "production": "large"},
    {"name": "Greenbushes", "lat": -33.85, "lon": 116.07, "type": "lithium", "commodity": "lithium", "country": "Australia", "production": "massive"},
    {"name": "Salar de Atacama", "lat": -23.50, "lon": -68.25, "type": "lithium", "commodity": "lithium", "country": "Chile", "production": "massive"},
    {"name": "Pilgangoora", "lat": -21.32, "lon": 119.05, "type": "lithium", "commodity": "lithium", "country": "Australia", "production": "large"},
    {"name": "Mount Weld", "lat": -28.77, "lon": 122.55, "type": "rare_earth", "commodity": "rare_earth", "country": "Australia", "production": "large"},
    {"name": "Bayan Obo", "lat": 41.80, "lon": 109.97, "type": "rare_earth", "commodity": "rare_earth", "country": "China", "production": "massive"},
    {"name": "Mountain Pass", "lat": 35.47, "lon": -115.53, "type": "rare_earth", "commodity": "rare_earth", "country": "USA", "production": "medium"},
    {"name": "Cannington", "lat": -21.87, "lon": 140.90, "type": "silver", "commodity": "silver", "country": "Australia", "production": "large"},
    {"name": "Fresnillo", "lat": 23.18, "lon": -102.87, "type": "silver", "commodity": "silver", "country": "Mexico", "production": "massive"},
    {"name": "Dukat", "lat": 62.57, "lon": 155.68, "type": "silver", "commodity": "silver", "country": "Russia", "production": "large"},
    {"name": "Antamina", "lat": -9.55, "lon": -77.07, "type": "copper/zinc", "commodity": "copper", "country": "Peru", "production": "large"},
    {"name": "Oyu Tolgoi", "lat": 43.00, "lon": 106.85, "type": "copper/gold", "commodity": "copper", "country": "Mongolia", "production": "massive"},
]

PIPELINES: list[dict] = [
    {"name": "Druzhba", "type": "oil", "color": "#e8730e", "coords": [[52.2, 40.2], [52.0, 30.5], [50.0, 20.0]]},
    {"name": "Nord Stream (inactive)", "type": "gas", "color": "#58a6ff", "coords": [[59.9, 30.3], [54.5, 13.0]]},
    {"name": "TAP", "type": "gas", "color": "#58a6ff", "coords": [[40.5, 20.0], [40.6, 18.5], [41.0, 16.0]]},
    {"name": "BTC (Baku-Tbilisi-Ceyhan)", "type": "oil", "color": "#e8730e", "coords": [[40.4, 49.9], [41.7, 44.8], [36.8, 36.0]]},
    {"name": "Keystone XL", "type": "oil", "color": "#e8730e", "coords": [[50.5, -108.0], [41.0, -97.0], [29.8, -95.0]]},
    {"name": "Trans-Alaska", "type": "oil", "color": "#e8730e", "coords": [[70.3, -148.7], [63.8, -145.5], [60.8, -146.4]]},
    {"name": "TAPI", "type": "gas", "color": "#58a6ff", "coords": [[35.3, 62.2], [33.9, 68.3], [26.0, 68.3]]},
    {"name": "East-West Pipeline", "type": "oil", "color": "#e8730e", "coords": [[26.0, 50.0], [21.5, 39.2]]},
]

LNG_TERMINALS: list[dict] = [
    {"name": "Sabine Pass", "lat": 29.73, "lon": -93.85, "type": "export", "country": "USA"},
    {"name": "Cove Point", "lat": 38.40, "lon": -76.40, "type": "export", "country": "USA"},
    {"name": "Freeport LNG", "lat": 28.95, "lon": -95.30, "type": "export", "country": "USA"},
    {"name": "Montoir-de-Bretagne", "lat": 47.30, "lon": -2.15, "type": "import", "country": "France"},
    {"name": "Swinoujscie", "lat": 53.91, "lon": 14.26, "type": "import", "country": "Poland"},
    {"name": "Gate Terminal", "lat": 51.95, "lon": 4.03, "type": "import", "country": "Netherlands"},
]

SHIPPING_LANES: list[dict] = [
    {"name": "Strait of Hormuz", "color": "#e8730e", "coords": [[26.6, 56.2], [25.5, 57.0], [24.5, 58.5]]},
    {"name": "Suez Canal", "color": "#58a6ff", "coords": [[31.3, 32.3], [30.5, 32.5], [29.9, 32.6]]},
    {"name": "Strait of Malacca", "color": "#58a6ff", "coords": [[6.5, 100.0], [2.5, 102.0], [1.3, 103.8]]},
    {"name": "Cape of Good Hope", "color": "#e8730e", "coords": [[-34.4, 18.5], [-35.0, 20.0], [-34.0, 26.0]]},
]
