
from datetime import datetime

# Import sample data
from sample import sample_data
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


ACCURACY_METRIC_DESIRED = True

# Parse data to compare accuracy
def accuracy_preparation(json_data):
    if json_data["sales_history"]:
        most_recent_transaction = json_data["sales_history"].pop(0)  # Removes and stores the first (latest) entry
        formatted_date = datetime.strptime(most_recent_transaction["date"], "%Y-%m-%d %H:%M:%S").strftime("%B, %Y")
    
    return most_recent_transaction["price_usd"], formatted_date, json_data

if ACCURACY_METRIC_DESIRED:
    ACTUAL_VALUE, DATE_TO_PREDICT, sample_data = accuracy_preparation(sample_data)
    
print(
        "ACTUAL VALUE", ACTUAL_VALUE, 
        "PREDICTED FUCKER", DATE_TO_PREDICT, 
        sample_data)