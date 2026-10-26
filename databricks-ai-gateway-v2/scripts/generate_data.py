"""Generate synthetic e-commerce data and load into Databricks Bronze schema."""

import os
import sys
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
load_dotenv()

from src.db_connection import run_query

CATALOG = "test_catalog"
BRONZE = f"{CATALOG}.bronze"
random.seed(42)

# --- Product catalog ---
CATEGORIES = {
    "Electronics": [
        ("Wireless Headphones", "SoundMax", 79.99),
        ("Bluetooth Speaker", "SoundMax", 49.99),
        ("USB-C Hub", "TechLink", 34.99),
        ("Mechanical Keyboard", "KeyPro", 129.99),
        ("Gaming Mouse", "KeyPro", 59.99),
        ("Webcam HD", "VisionTech", 89.99),
        ("Laptop Stand", "ErgoDesk", 45.99),
        ("Power Bank 20000mAh", "ChargePlus", 39.99),
        ("Noise Cancelling Earbuds", "SoundMax", 149.99),
        ("Monitor 27 inch", "VisionTech", 349.99),
    ],
    "Clothing": [
        ("Cotton T-Shirt", "UrbanWear", 24.99),
        ("Denim Jeans", "UrbanWear", 59.99),
        ("Running Shoes", "SprintFit", 89.99),
        ("Winter Jacket", "NorthStyle", 149.99),
        ("Casual Sneakers", "SprintFit", 69.99),
        ("Polo Shirt", "UrbanWear", 34.99),
        ("Yoga Pants", "FlexFit", 44.99),
        ("Hoodie", "NorthStyle", 54.99),
    ],
    "Home & Kitchen": [
        ("Coffee Maker", "BrewMaster", 79.99),
        ("Air Fryer", "CookEasy", 99.99),
        ("Blender", "CookEasy", 49.99),
        ("Toaster", "BrewMaster", 29.99),
        ("Knife Set", "ChefPro", 69.99),
        ("Cutting Board", "ChefPro", 19.99),
        ("Water Bottle", "HydroFit", 14.99),
        ("Food Storage Set", "FreshKeep", 24.99),
    ],
    "Sports": [
        ("Yoga Mat", "FlexFit", 29.99),
        ("Resistance Bands", "FlexFit", 19.99),
        ("Dumbbell Set", "IronGrip", 79.99),
        ("Jump Rope", "IronGrip", 12.99),
        ("Fitness Tracker", "TrackFit", 129.99),
        ("Sports Water Bottle", "HydroFit", 9.99),
    ],
    "Books": [
        ("Python Programming", "TechBooks", 44.99),
        ("Data Engineering Guide", "TechBooks", 54.99),
        ("Machine Learning Basics", "TechBooks", 49.99),
        ("Business Strategy", "BizPress", 29.99),
        ("Fiction Bestseller", "NovelHouse", 14.99),
        ("Cookbook Essentials", "FoodPrint", 24.99),
    ],
    "Beauty": [
        ("Face Moisturizer", "GlowUp", 34.99),
        ("Sunscreen SPF50", "GlowUp", 19.99),
        ("Hair Dryer", "StylePro", 59.99),
        ("Perfume", "LuxScent", 89.99),
    ],
}

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Christopher", "Karen", "Charles", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Steven", "Ashley",
    "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna", "Kenneth", "Michelle",
    "Kevin", "Dorothy", "Brian", "Carol", "George", "Amanda", "Timothy", "Melissa",
    "Ronald", "Deborah", "Edward", "Stephanie", "Jason", "Rebecca", "Jeffrey", "Sharon",
    "Ryan", "Laura", "Jacob", "Cynthia", "Gary", "Kathleen", "Nicholas", "Amy",
    "Eric", "Angela", "Jonathan", "Shirley", "Stephen", "Anna", "Larry", "Brenda",
    "Justin", "Pamela", "Scott", "Emma", "Brandon", "Nicole", "Benjamin", "Helen",
    "Samuel", "Samantha", "Raymond", "Katherine", "Gregory", "Christine", "Frank", "Debra",
    "Alexander", "Rachel", "Patrick", "Carolyn", "Jack", "Janet", "Dennis", "Catherine",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter",
    "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz", "Edwards",
    "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy", "Cook", "Rogers",
]

CITIES_STATES = [
    ("New York", "NY"), ("Los Angeles", "CA"), ("Chicago", "IL"), ("Houston", "TX"),
    ("Phoenix", "AZ"), ("Philadelphia", "PA"), ("San Antonio", "TX"), ("San Diego", "CA"),
    ("Dallas", "TX"), ("San Jose", "CA"), ("Austin", "TX"), ("Jacksonville", "FL"),
    ("Fort Worth", "TX"), ("Columbus", "OH"), ("Charlotte", "NC"), ("Indianapolis", "IN"),
    ("San Francisco", "CA"), ("Seattle", "WA"), ("Denver", "CO"), ("Nashville", "TN"),
    ("Portland", "OR"), ("Oklahoma City", "OK"), ("Las Vegas", "NV"), ("Memphis", "TN"),
    ("Louisville", "KY"), ("Baltimore", "MD"), ("Milwaukee", "WI"), ("Albuquerque", "NM"),
    ("Tucson", "AZ"), ("Fresno", "CA"), ("Sacramento", "CA"), ("Atlanta", "GA"),
    ("Miami", "FL"), ("Raleigh", "NC"), ("Omaha", "NE"), ("Minneapolis", "MN"),
]

PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "bank_transfer", "gift_card"]
ORDER_STATUSES = ["completed", "shipped", "processing", "cancelled", "returned"]
SOURCE_SYSTEMS = ["web_app", "mobile_app", "pos_terminal", "partner_api"]
REGIONS = ["East", "West", "North", "South", "Central"]


def generate_products():
    products = []
    pid = 1
    for category, items in CATEGORIES.items():
        for name, brand, price in items:
            if random.random() < 0.04:
                price = 0.0 if random.random() < 0.5 else -abs(price)
            products.append((pid, name, category, brand, round(price, 2), round(random.uniform(0.1, 15.0), 2)))
            pid += 1
    return products


def generate_customers(n=200):
    customers = []
    for cid in range(1, n + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        city, state = random.choice(CITIES_STATES)
        email = f"{first.lower()}.{last.lower()}{cid}@example.com"
        phone = f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        signup = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 700))

        if random.random() < 0.05:
            email = None
        if random.random() < 0.03:
            phone = None

        customers.append((cid, first, last, email, phone, city, state, "US",
                          signup.strftime("%Y-%m-%d"), random.choice(SOURCE_SYSTEMS)))
    return customers


def generate_orders(n=5000, num_customers=200, num_products=50):
    orders = []
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    date_range = (end_date - start_date).days

    for oid in range(1, n + 1):
        cust_id = random.randint(1, num_customers)
        prod_id = random.randint(1, num_products)
        qty = random.randint(1, 10)
        order_date = start_date + timedelta(days=random.randint(0, date_range))
        status = random.choices(ORDER_STATUSES, weights=[60, 20, 10, 7, 3])[0]
        payment = random.choice(PAYMENT_METHODS)
        source = random.choice(SOURCE_SYSTEMS)
        region = random.choice(REGIONS)

        if random.random() < 0.03:
            cust_id = random.randint(900, 999)
        if random.random() < 0.03:
            prod_id = random.randint(900, 999)
        if random.random() < 0.02:
            qty = None
        if random.random() < 0.01:
            qty = -abs(random.randint(1, 5))
        if random.random() < 0.01:
            order_date = datetime(2026, random.randint(1, 12), random.randint(1, 28))
        if random.random() < 0.01:
            date_str = "INVALID"
        else:
            date_str = order_date.strftime("%Y-%m-%d")
        if random.random() < 0.02:
            region = None

        orders.append((oid, cust_id, prod_id, qty, date_str, status, payment, source, region))

    for _ in range(100):
        dup_id = random.randint(1, n)
        original = next((o for o in orders if o[0] == dup_id), None)
        if original:
            orders.append(original)

    random.shuffle(orders)
    return orders


def escape(val):
    if val is None:
        return "NULL"
    if isinstance(val, str):
        return "'" + val.replace("'", "\\'") + "'"
    return str(val)


def batch_insert_with_ts(table, columns, rows, batch_size=100):
    total = len(rows)
    all_cols = columns + ["ingested_at"]
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        values = ",\n        ".join(
            "(" + ", ".join(escape(v) for v in row) + ", current_timestamp())" for row in batch
        )
        run_query(f"INSERT INTO {table} ({', '.join(all_cols)}) VALUES\n        {values}")
        done = min(i + batch_size, total)
        print(f"  {done}/{total} rows inserted", end="\r")
    print()


def create_schemas():
    print("=== CREATING SCHEMAS ===\n")
    for schema in ["bronze", "silver", "gold"]:
        run_query(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{schema}")
        print(f"  Created schema: {CATALOG}.{schema}")
    print()


def create_products_table(products):
    print("=== BRONZE: raw_products ===")
    run_query(f"DROP TABLE IF EXISTS {BRONZE}.raw_products")
    run_query(f"""
        CREATE TABLE {BRONZE}.raw_products (
            product_id   INT,
            product_name STRING,
            category     STRING,
            brand        STRING,
            unit_price   DOUBLE,
            weight_kg    DOUBLE,
            source_system STRING,
            ingested_at  TIMESTAMP
        )
    """)
    rows = [(p[0], p[1], p[2], p[3], p[4], p[5], random.choice(SOURCE_SYSTEMS)) for p in products]
    cols = ["product_id", "product_name", "category", "brand", "unit_price", "weight_kg", "source_system"]

    values = ",\n        ".join(
        "(" + ", ".join(escape(v) for v in row) + ", current_timestamp())" for row in rows
    )
    run_query(f"INSERT INTO {BRONZE}.raw_products ({', '.join(cols)}, ingested_at) VALUES\n        {values}")
    print(f"  Inserted {len(rows)} products")


def create_customers_table(customers):
    print("\n=== BRONZE: raw_customers ===")
    run_query(f"DROP TABLE IF EXISTS {BRONZE}.raw_customers")
    run_query(f"""
        CREATE TABLE {BRONZE}.raw_customers (
            customer_id  INT,
            first_name   STRING,
            last_name    STRING,
            email        STRING,
            phone        STRING,
            city         STRING,
            state        STRING,
            country      STRING,
            signup_date  STRING,
            source_system STRING,
            ingested_at  TIMESTAMP
        )
    """)
    cols = ["customer_id", "first_name", "last_name", "email", "phone",
            "city", "state", "country", "signup_date", "source_system"]
    batch_insert_with_ts(f"{BRONZE}.raw_customers", cols, customers)
    print(f"  Inserted {len(customers)} customers")


def create_orders_table(orders):
    print("\n=== BRONZE: raw_orders ===")
    run_query(f"DROP TABLE IF EXISTS {BRONZE}.raw_orders")
    run_query(f"""
        CREATE TABLE {BRONZE}.raw_orders (
            order_id       INT,
            customer_id    INT,
            product_id     INT,
            quantity        INT,
            order_date     STRING,
            order_status   STRING,
            payment_method STRING,
            source_system  STRING,
            region         STRING,
            ingested_at    TIMESTAMP
        )
    """)
    cols = ["order_id", "customer_id", "product_id", "quantity", "order_date",
            "order_status", "payment_method", "source_system", "region"]
    batch_insert_with_ts(f"{BRONZE}.raw_orders", cols, orders)
    print(f"  Inserted {len(orders)} orders")


if __name__ == "__main__":
    print("Generating synthetic e-commerce data...\n")

    create_schemas()

    products = generate_products()
    print(f"Generated {len(products)} products")

    customers = generate_customers(200)
    print(f"Generated {len(customers)} customers")

    orders = generate_orders(5000, 200, len(products))
    print(f"Generated {len(orders)} orders (including duplicates)\n")

    create_products_table(products)
    create_customers_table(customers)
    create_orders_table(orders)

    print("\n=== VERIFICATION ===")
    for table in ["raw_products", "raw_customers", "raw_orders"]:
        _, rows = run_query(f"SELECT COUNT(*) FROM {BRONZE}.{table}")
        print(f"  {BRONZE}.{table}: {rows[0][0]} rows")

    print("\nBronze layer loaded successfully!")
