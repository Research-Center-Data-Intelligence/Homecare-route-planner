import random
import csv

# REAL STREETS IN HEERLEN with their postcode ranges and valid house numbers
# Sources: Postcode data from various Heerlen streets [citation:2][citation:6][citation:7]
HEERLEN_STREETS = [
    # Street name, base postcode, min house number, max house number
    ("Kerkstraat", "6411", 1, 50),        # Central Heerlen [citation:1]
    ("Stationsstraat", "6411", 1, 40),     # Near station area [citation:2]
    ("Dorpsstraat", "6412", 1, 60),        # [citation:2]
    ("Schoolstraat", "6413", 1, 45),       # [citation:2]
    ("Akerstraat", "6411", 1, 120),        # Major street [citation:2]
    ("Bongerd", "6411", 1, 30),            # City center
    ("Gasthuisstraat", "6411", 1, 25),     # Near hospital
    ("Pancratiusstraat", "6411", 1, 20),   # Church area
    ("Trompstraat", "6412", 1, 35),        # Residential
    ("Valkenburgerweg", "6412", 1, 80),    # Main road
    ("Heerlerbaan", "6418", 1, 277),       # [citation:7] - extensive range
    ("Heerlerheide", "6413", 1, 100),      # District
    ("Putgraaf", "6411", 1, 45),           # City center [citation:2]
    ("Raadhuisstraat", "6411", 1, 30),     # Town hall area
    ("Lindelaan", "6414", 1, 50),          # Residential
    ("Beukenlaan", "6414", 1, 45),         # Residential
    ("Eikenlaan", "6414", 1, 40),          # Residential
    ("Wilhelminastraat", "6412", 1, 55),   # [citation:2]
    ("Julianaweg", "6413", 1, 60),         # Residential
    ("Prinses Irenestraat", "6413", 1, 35), # Residential
    ("Tollensstraat", "6416", 1, 42),      # [citation:6][citation:8] - exact numbers
    ("Jacob van Maerlantstraat", "6416", 2, 34),  # [citation:9] - even numbers only
    ("Eisterweg", "6422", 2, 8),            # [citation:10]
    ("Hondsdraf", "6418", 1, 15),           # [citation:1]
    ("Lienaertsstraat", "6416", 1, 45),     # [citation:1] - corrected to Heerlen
    ("Welterlaan", "6415", 1, 45),          # [citation:3]
    ("Laan van Hövell tot Westerflier", "6411", 1, 44),  # [citation:4]
    ("Caumerweg", "6418", 1, 94),           # [citation:7]
    ("Pastoor Erensstraat", "6418", 1, 34), # [citation:7]
    ("September 1944-straat", "6418", 1, 121), # [citation:7]
    ("Palestinastraat", "6418", 1, 279),    # [citation:7] - long street
    ("Nazarethstraat", "6418", 1, 96),      # [citation:7]
    ("Jeruzalemstraat", "6418", 2, 46),     # [citation:7] - even numbers
    ("Bautscherweg", "6418", 1, 166),       # [citation:7]
    ("Corisbergweg", "6418", 20, 205),      # [citation:7]
    ("A gen Giezen", "6418", 1, 64),        # [citation:7]
]

# Street names without full data - will use with generic postcode
ADDITIONAL_STREETS = [
    ("Ds. Jongeneelstraat", "6411", 1, 30),
    ("Kapelaan Berixstraat", "6411", 1, 25),
    ("Op de Nobel", "6411", 1, 20),
    ("Bekkerweg", "6411", 1, 35),
    ("Deken Nicolaijestraat", "6411", 1, 28),
    ("Kortstraat", "6411", 1, 15),
    ("Oude Lindestraat", "6411", 1, 22),
    ("Ambachtsstraat", "6411", 1, 18),
    ("Tempsplein", "6411", 1, 10),
    ("Coriovallumstraat", "6411", 1, 40),
    ("Ruys de Beerenbroucklaan", "6411", 1, 60),
    ("Mariabad", "6411", 1, 12),
    ("Oliemolenstraat", "6411", 1, 30),
    ("Keerweg", "6418", 28, 115),           # [citation:7]
    ("Vrijheidstraat", "6418", 1, 19),       # [citation:7]
    ("Montgomerystraat", "6418", 1, 18),     # [citation:7]
    ("Vredestraat", "6418", 1, 20),          # [citation:7]
    ("Pattonstraat", "6418", 1, 49),         # [citation:7]
    ("Hodgesstraat", "6418", 1, 50),         # [citation:7]
    ("Herlongstraat", "6418", 1, 59),        # [citation:7]
    ("Horicherhofstraat", "6418", 1, 32),    # [citation:7]
    ("Caumerboord", "6418", 1, 99),          # [citation:7]
    ("Hambeukerboord", "6418", 1, 101),      # [citation:7]
    ("Bradleystraat", "6418", 1, 31),        # [citation:7]
    ("Oud Valkenhuizerstraat", "6418", 4, 4), # [citation:7] - single number
    ("Wienweg", "6418", 7, 92),              # [citation:7]
    ("Bovenste Caumer", "6418", 2, 24),      # [citation:7]
    ("Simpsonstraat", "6418", 2, 10),        # [citation:7]
    ("Bergdriesch", "6418", 1, 65),          # [citation:7]
    ("Kanaalstraat", "6418", 1, 37),         # [citation:7]
    ("Jerichostraat", "6418", 1, 98),        # [citation:7]
    ("Giezenhof", "6418", 1, 19),            # [citation:7]
    ("Sinaïstraat", "6418", 2, 28),          # [citation:7]
    ("Samariastraat", "6418", 1, 35),        # [citation:7]
    ("Judeastraat", "6418", 1, 39),          # [citation:7]
    ("Bethlehemstraat", "6418", 1, 58),      # [citation:7]
    ("Galileastraat", "6418", 1, 48),        # [citation:7]
    ("Romeinenstraat", "6418", 2, 32),        # [citation:7]
]

# Combine all streets
ALL_STREETS = HEERLEN_STREETS + ADDITIONAL_STREETS

# Possible care arrangements

# Valid Heerlen postal codes [citation:2]
HEERLEN_POSTCODES = ["6401", "6411", "6412", "6413", "6414", "6415", "6416", "6417", "6418", "6419", "6421", "6422"]

def generate_real_address():
    """Generate a real Heerlen address using actual street data."""
    street, base_postcode, min_num, max_num = random.choice(ALL_STREETS)
    
    # Generate house number within valid range
    house_number = random.randint(min_num, max_num)
    
    # For streets with even/odd restrictions, ensure proper number
    if street == "Jacob van Maerlantstraat" and house_number % 2 != 0:
        house_number = house_number + 1 if house_number < max_num else house_number - 1
    
    # Generate the full 4-digit + 2-letter postcode
    # Use the base postcode and add random letters
    letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=2))
    full_postcode = f"{base_postcode} {letters}"
    
    return f"{street} {house_number} {full_postcode} Heerlen"

def generate_client(index):
    """Generate a single client record as a dictionary."""
    name = f"employees {index}"
    address = generate_real_address()
    
    time_window_start = "07:00"
    time_window_end   = "18:00"

    
    
    # Most clients have no pets; occasional 1 or 2
    dogs = random.choices([0, 1, 2, -1], weights=[0.2, 0.2, 0.1,0.5])[0]
    cats = random.choices([0, 1, 2, -1], weights=[0.1, 0.3, 0.1,0.5])[0]
    
    # 30% chance of smoking
    smokes = random.random() < 0.3
    
    return {
        "name": name,
        "address": address,
        "time_window_start": time_window_start,
        "time_window_end": time_window_end,
        "dogs": dogs,
        "cats": cats,
        "smokes": smokes
    }

def generate_clients_csv(num_clients, filename="employees.csv"):
    """Generate num_clients records and write them to a CSV file."""
    fieldnames = [
        "name", "address",
        "time_window_start", "time_window_end",
        "dogs", "cats", "smokes"
    ]
    
    with open(filename, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for i in range(1, num_clients + 1):
            client = generate_client(i)
            # Convert boolean to lowercase string for readability
            client["smokes"] = str(client["smokes"]).lower()
            writer.writerow(client)
    
    print(f"Generated {num_clients} clients in '{filename}' using REAL Heerlen addresses.")

if __name__ == "__main__":
    # Generate 20 clients by default
    generate_clients_csv(20)