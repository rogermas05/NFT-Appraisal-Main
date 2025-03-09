from Backend.AI.functions.metadata import generate_metadata, parse_nft_data, get_nft_sales_history
from firebase_functions import https_fn, options
from firebase_admin import initialize_app
from moralis import evm_api
from dotenv import load_dotenv
import os
import requests
from datetime import datetime
import json

# Initialize Firebase
initialize_app()

# Initialize Moralis
MORALIS_API_KEY = os.getenv('MORALIS_API')
# or alternatively:
# MORALIS_API_KEY = os.environ.get('K_SERVICE') and json.loads(os.environ.get('FIREBASE_CONFIG')).get('moralis', {}).get('api_key')

if not MORALIS_API_KEY:
    raise ValueError("Moralis API key not found in Firebase config")

evm_api.api_key = MORALIS_API_KEY

@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins=['*'],
        cors_methods=['GET', 'POST']
    )
)
def get_nft_data(req: https_fn.Request) -> https_fn.Response:
    # Get parameters from URL query parameters
    contract_address = req.args.get('contract_address')
    token_id = req.args.get('token_id')
    
    if not contract_address or not token_id:
        return https_fn.Response(
            response=json.dumps({'error': 'Missing contract_address or token_id'}),
            status=400,
            content_type='application/json'
        )

    try:
        result = main(contract_address, token_id)
        return https_fn.Response(
            response=json.dumps(result),
            status=200,
            content_type='application/json'
        )
    except Exception as e:
        return https_fn.Response(
            response=json.dumps({'error': str(e)}),
            status=500,
            content_type='application/json'
        )

def main(contract_address, token_id):
    api_key = os.getenv('RESERVOIR_API')
    metadata = generate_metadata(contract_address, token_id)
    
    all_sales = []
    continuation = None
    
    while True:
        sales, continuation = get_nft_sales_history(contract_address, token_id, api_key, continuation)
        if not sales:
            break
            
        for sale in sales:
            price_eth = float(sale['price']['amount']['native']) if sale['price'] else 0
            price_usd = float(sale['price']['amount']['usd']) if sale['price'] else 0
            timestamp = datetime.fromtimestamp(sale['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            all_sales.append({
                'price_ethereum': price_eth,
                'price_usd': price_usd,
                'date': timestamp
            })
            
        if not continuation:
            break
    
    metadata['sales_history'] = all_sales
    json = parse_nft_data(metadata)
    return json