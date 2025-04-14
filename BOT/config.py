# API_TOKEN="ваш-токен"
# ADMIN_ID=1234567890 # Ваш ID (@userinfobot)

import os

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
