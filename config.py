ZONE_KEYWORDS = {
    "red":[
        # Chemical & Processing Hazards
        "hazard","chemical","furnace","toxic","danger","poison","lab","reactor",
        "chemical processing","chemical storage","raw material","processing complex",
        # Fire Detection & Suppression
        "fire extinguisher","sprinkler","alarm","hazmat","flammable","explosive",
        "combustible","ignition","foam","suppression","fire alarm","detection",
        "hazard zone","fire detection system",
        # High Temperature & Combustion
        "furnace complex","high temperature","combustion","thermal hazard",
        # Storage Areas (High Fire Risk)
        "storage","warehouse","material storage","packaging storage","supply room",
        "stockroom","inventory","combustible storage"
    ],
    "orange":[
        # Electrical Infrastructure
        "electrical","power","electric","hvac","generator","panel","transformer",
        "switch","outlet","circuit","wiring","fuse","short circuit","voltage",
        "distribution","electrical fire","control room",
        # Data & Communication Facilities
        "server","data center","server room","network room","equipment room",
        "telecommunications","server farm","control center",
        # High-Power Systems
        "electrical substation","power distribution","backup power","ups",
        "distribution board","electrical panel","control panel"
    ],
    "yellow":[
        # Food Service & Cooking Areas
        "kitchen","canteen","food","cafeteria","dining","breakroom","break room",
        "cafe","pantry","catering",
        # Fire Suppression in Cooking
        "fire suppression","ventilation","exhaust","hood","cooking hood",
        # Flammable Materials
        "gas","propane","oil","grease","stove","grill","cooking equipment",
        "lpg","fuel","combustible materials",
        # Laundry & Maintenance
        "laundry room","maintenance","cleaning supplies","utility room"
    ],
    "green":[
        # Emergency Exits & Evacuation
        "exit","emergency exit","emergency stair","stair","staircase","stairwell",
        "evacuation route","evacuation","escape route",
        # Assembly & Refuge Areas
        "assembly point","muster point","refuge area","refuge room","shelter",
        "safe room","outdoor garden","outdoor area","safe zone",
        # Safety & Medical
        "medical","first aid","first aid station","defibrillator","oxygen",
        "emergency medical","health center",
        # Restroom & Facilities
        "restroom","bathroom","washroom","toilet","lavatory",
        # General Safe Spaces
        "safe","reception area","reception","hallway","corridor","open space",
        "open workspace","office","consulting room","conference room"
    ]
}

# Only these factory-room terms can create a room record. Add terms here for
# room names used in future blueprints.
ROOM_KEYWORDS = {
    "red": ["chemical storage", "chemical processing", "chemical", "furnace room", "furnace complex", "furnace", "laboratory", "lab", "raw material", "material storage", "storage room", "warehouse", "stores", "packaging"],
    "orange": ["electrical room", "hvlv electrical", "electrical", "substation", "power room", "server room", "server", "data center", "central data", "control room", "process control", "backup generator", "generator"],
    "yellow": ["kitchen", "canteen", "cafeteria", "break room", "pantry", "laundry", "maintenance room", "utility room"],
    "green": ["office", "emergency exit", "first aid station", "first aid", "locker room", "locker", "outdoor garden", "garden", "reception", "conference room", "meeting room", "restroom", "bathroom"],
}

# Blueprint dashboards/titles/OCR counters never represent physical rooms.
NON_ROOM_KEYWORDS = ["system warning", "safety violation", "plant metric", "total", "zone", "nominal", "current load", "power usage", "primary feed", "quality", "tested", "client", "date", "page"]
