# Databricks notebook source
# MAGIC %md
# MAGIC # 01 - Generate Bronze Layer
# MAGIC
# MAGIC Generates synthetic data and loads the Bronze tables. Orders are appended on every
# MAGIC run so the fact table keeps growing; customers and products are seeded once (not
# MAGIC duplicated). No fixed seed and run-relative dates, so each batch is different.
# MAGIC Catalog, schema and row counts are widget parameters.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

dbutils.widgets.text("catalog", "test_catalog", "Catalog")
dbutils.widgets.text("schema", "default", "Schema")
dbutils.widgets.text("num_customers", "200", "Number of customers")
dbutils.widgets.text("num_orders", "5000", "Number of orders")

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
NUM_CUSTOMERS = int(dbutils.widgets.get("num_customers"))
NUM_ORDERS = int(dbutils.widgets.get("num_orders"))

FQ = f"{CATALOG}.{SCHEMA}"
print(f"Target: {FQ}  |  customers={NUM_CUSTOMERS}  orders={NUM_ORDERS}")

# COMMAND ----------

import random
from datetime import datetime, timedelta

from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, IntegerType, StringType, DoubleType,
)

RUN_TS = datetime.now()
LOOKBACK_DAYS = 365

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reference data (product catalog, names, locations)

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generators

# COMMAND ----------

def generate_products():
    products = []
    pid = 1
    for category, items in CATEGORIES.items():
        for name, brand, price in items:
            # ~4% of products get a price issue (0 or negative)
            if random.random() < 0.04:
                price = 0.0 if random.random() < 0.5 else -abs(price)
            products.append((pid, name, category, brand, round(price, 2),
                             round(random.uniform(0.1, 15.0), 2), random.choice(SOURCE_SYSTEMS)))
            pid += 1
    return products


def generate_customers(n):
    customers = []
    for cid in range(1, n + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        city, state = random.choice(CITIES_STATES)
        email = f"{first.lower()}.{last.lower()}{cid}@example.com"
        phone = f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        signup = RUN_TS - timedelta(days=random.randint(0, 730))

        if random.random() < 0.05:   # ~5% NULL email
            email = None
        if random.random() < 0.03:   # ~3% NULL phone
            phone = None

        customers.append((cid, first, last, email, phone, city, state, "US",
                          signup.strftime("%Y-%m-%d"), random.choice(SOURCE_SYSTEMS)))
    return customers


def generate_orders(n, num_customers, num_products, start_id=0):
    orders = []
    for i in range(1, n + 1):
        oid = start_id + i
        cust_id = random.randint(1, num_customers)
        prod_id = random.randint(1, num_products)
        qty = random.randint(1, 10)
        order_date = RUN_TS - timedelta(days=random.randint(0, LOOKBACK_DAYS))
        status = random.choices(ORDER_STATUSES, weights=[60, 20, 10, 7, 3])[0]
        payment = random.choice(PAYMENT_METHODS)
        source = random.choice(SOURCE_SYSTEMS)
        region = random.choice(REGIONS)

        if random.random() < 0.03:   # ~3% reference non-existent customer
            cust_id = random.randint(900, 999)
        if random.random() < 0.03:   # ~3% reference non-existent product
            prod_id = random.randint(900, 999)
        if random.random() < 0.02:   # ~2% NULL quantity
            qty = None
        if random.random() < 0.01:   # ~1% negative quantity
            qty = -abs(random.randint(1, 5))
        if random.random() < 0.01:   # ~1% future date
            order_date = RUN_TS + timedelta(days=random.randint(1, 60))

        if random.random() < 0.01:   # ~1% bad date string
            date_str = "INVALID"
        else:
            date_str = order_date.strftime("%Y-%m-%d")

        if random.random() < 0.02:   # ~2% NULL region
            region = None

        orders.append((oid, cust_id, prod_id, qty, date_str, status, payment, source, region))

    # ~100 duplicate orders (reuse existing order_ids)
    existing = list(orders)
    for _ in range(100):
        orders.append(random.choice(existing))

    random.shuffle(orders)
    return orders

# COMMAND ----------

# MAGIC %md
# MAGIC ## Schemas & writer

# COMMAND ----------

PRODUCTS_SCHEMA = StructType([
    StructField("product_id", IntegerType(), False),
    StructField("product_name", StringType(), True),
    StructField("category", StringType(), True),
    StructField("brand", StringType(), True),
    StructField("unit_price", DoubleType(), True),
    StructField("weight_kg", DoubleType(), True),
    StructField("source_system", StringType(), True),
])

CUSTOMERS_SCHEMA = StructType([
    StructField("customer_id", IntegerType(), False),
    StructField("first_name", StringType(), True),
    StructField("last_name", StringType(), True),
    StructField("email", StringType(), True),
    StructField("phone", StringType(), True),
    StructField("city", StringType(), True),
    StructField("state", StringType(), True),
    StructField("country", StringType(), True),
    StructField("signup_date", StringType(), True),
    StructField("source_system", StringType(), True),
])

ORDERS_SCHEMA = StructType([
    StructField("order_id", IntegerType(), False),
    StructField("customer_id", IntegerType(), True),
    StructField("product_id", IntegerType(), True),
    StructField("quantity", IntegerType(), True),
    StructField("order_date", StringType(), True),
    StructField("order_status", StringType(), True),
    StructField("payment_method", StringType(), True),
    StructField("source_system", StringType(), True),
    StructField("region", StringType(), True),
])


def table_count(table):
    try:
        return spark.table(f"{FQ}.{table}").count()
    except Exception:
        return 0


def write_bronze(rows, schema_def, table, mode):
    df = (
        spark.createDataFrame(rows, schema_def)
        .withColumn("ingested_at", F.current_timestamp())
    )
    writer = df.write.mode(mode)
    if mode == "overwrite":
        writer = writer.option("overwriteSchema", "true")
    writer.saveAsTable(f"{FQ}.{table}")
    return df.count()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate & load Bronze

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ}")

# Dimensions (products, customers) are seeded once. Re-running must not duplicate them,
# so load only when the table is empty.
if table_count("raw_products") == 0:
    n = write_bronze(generate_products(), PRODUCTS_SCHEMA, "raw_products", "overwrite")
    print(f"  raw_products seeded: {n} rows")
else:
    print(f"  raw_products: {table_count('raw_products')} rows (already seeded, left as is)")

if table_count("raw_customers") == 0:
    n = write_bronze(generate_customers(NUM_CUSTOMERS), CUSTOMERS_SCHEMA, "raw_customers", "overwrite")
    print(f"  raw_customers seeded: {n} rows")
else:
    print(f"  raw_customers: {table_count('raw_customers')} rows (already seeded, left as is)")

# Orders are the growing fact table: every run APPENDS a new batch, with order_id
# continuing after the current maximum so ids stay unique across runs.
num_customers = table_count("raw_customers")
num_products = table_count("raw_products")
start_id = 0
if table_count("raw_orders"):
    start_id = spark.sql(f"SELECT MAX(order_id) AS m FROM {FQ}.raw_orders").collect()[0]["m"] or 0

orders = generate_orders(NUM_ORDERS, num_customers, num_products, start_id)
added = write_bronze(orders, ORDERS_SCHEMA, "raw_orders", "append")
print(f"  raw_orders appended: +{added} rows (total {table_count('raw_orders')})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify

# COMMAND ----------

for t in ["raw_products", "raw_customers", "raw_orders"]:
    cnt = spark.table(f"{FQ}.{t}").count()
    print(f"  {FQ}.{t}: {cnt} rows")

print("\nBronze layer loaded successfully.")

# COMMAND ----------

dbutils.notebook.exit(
    f"bronze_loaded orders_total={table_count('raw_orders')} "
    f"customers={table_count('raw_customers')} products={table_count('raw_products')}"
)
