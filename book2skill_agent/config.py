import os

# API Configuration
API_KEY = ""
BASE_URL = ""
MODEL_NAME = "deepseek-v4-flash"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Path Configuration
OUTPUT_DIR = os.path.join(BASE_DIR, "books")

# Prompts Directory
PROMPTS_DIR = os.path.join(BASE_DIR, "book2skill", "extractors")
TEMPLATES_DIR = os.path.join(BASE_DIR, "book2skill", "templates")
