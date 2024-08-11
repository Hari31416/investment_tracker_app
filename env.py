from dotenv import load_dotenv
import os

load_dotenv()

MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_HOST = os.getenv("MONGO_HOST")
MONGO_DB = os.getenv("MONGO_DB")
MONGO_USER_COLLECTION = os.getenv("MONGO_USER_COLLECTION", "users")
MONGO_MAPPING_COLLECTION = os.getenv("MONGO_MAPPING_COLLECTION", "mappings")
MONGO_TRANSACTIONS_COLLECTION = os.getenv(
    "MONGO_TRANSACTIONS_COLLECTION", "transactions"
)
