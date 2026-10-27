"""Alle capitals voor de schip-dropdown: (type-id, naam, klasse).

Eenmalig uit de SDE gehaald (gepubliceerde types in de capital-groepen), zodat de plugin ook
werkt op een server zonder SDE. Komt er een nieuw capital bij, dan hier toevoegen.
"""

SCHEPEN = [
    # Jump Freighter
    (28848, "Anshar", "jf"),
    (28850, "Ark", "jf"),
    (28846, "Nomad", "jf"),
    (28844, "Rhea", "jf"),
    # Carrier
    (23757, "Archon", "carrier"),
    (23915, "Chimera", "carrier"),
    (24483, "Nidhoggur", "carrier"),
    (23911, "Thanatos", "carrier"),
    # Dreadnought (incl. Lancers)
    (77283, "Bane", "dread"),
    (45647, "Caiman", "dread"),
    (42243, "Chemosh", "dread"),
    (77281, "Hubris", "dread"),
    (77284, "Karura", "dread"),
    (19724, "Moros", "dread"),
    (73792, "Moros Navy Issue", "dread"),
    (19722, "Naglfar", "dread"),
    (73787, "Naglfar Fleet Issue", "dread"),
    (19726, "Phoenix", "dread"),
    (73793, "Phoenix Navy Issue", "dread"),
    (19720, "Revelation", "dread"),
    (73790, "Revelation Navy Issue", "dread"),
    (87381, "Sarathiel", "dread"),
    (77288, "Valravn", "dread"),
    (42124, "Vehement", "dread"),
    (52907, "Zirnitra", "dread"),
    # Force Auxiliary
    (37604, "Apostle", "fax"),
    (42242, "Dagon", "fax"),
    (37606, "Lif", "fax"),
    (45645, "Loggerhead", "fax"),
    (37605, "Minokawa", "fax"),
    (37607, "Ninazu", "fax"),
    # Supercarrier
    (23919, "Aeon", "super"),
    (22852, "Hel", "super"),
    (23913, "Nyx", "super"),
    (3514, "Revenant", "super"),
    (42125, "Vendetta", "super"),
    (23917, "Wyvern", "super"),
    # Titan
    (11567, "Avatar", "titan"),
    (78576, "Azariel", "titan"),
    (671, "Erebus", "titan"),
    (45649, "Komodo", "titan"),
    (3764, "Leviathan", "titan"),
    (42241, "Molok", "titan"),
    (23773, "Ragnarok", "titan"),
    (42126, "Vanquisher", "titan"),
    # Capital Industrial
    (28352, "Rorqual", "rorqual"),
]

PER_ID = {type_id: (naam, klasse) for type_id, naam, klasse in SCHEPEN}

# Klassen zonder ship maintenance bay: daar vragen we geen SMB-ruimte.
ZONDER_SMB = {"jf"}
ZONDER_SMB_IDS = [type_id for type_id, _naam, klasse in SCHEPEN if klasse in ZONDER_SMB]


def keuzes():
    """Gegroepeerde choices voor een <select>: [(klasse-label, [(id, naam), ...]), ...]."""
    from .models import SchipType

    groepen = []
    for klasse, label in SchipType.choices:
        rij = [(type_id, naam) for type_id, naam, k in SCHEPEN if k == klasse]
        if rij:
            groepen.append((label, rij))
    return groepen
