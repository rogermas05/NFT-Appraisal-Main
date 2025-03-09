from moralis import evm_api
from dotenv import load_dotenv
import os
import requests
from datetime import datetime
import json
from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
# Enable CORS for all routes
CORS(app)

def generate_metadata(address, token_id):
    api_key = os.getenv('MORALIS_API')
    metadata_params = {
        "chain": "eth",
        "format": "decimal",
        "media_items": False,
        "normalize_metadata": True,
        "address": address,
        "token_id": token_id
    }

    metadata = evm_api.nft.get_nft_metadata(
        api_key=api_key,
        params=metadata_params,
    )
     
    return metadata

def get_nft_sales_history(contract_address, token_id, api_key, continuation=None):
    url = 'https://api.reservoir.tools/sales/v5'
    headers = {
        'x-api-key': api_key
    }
    params = {
        'tokens': f'{contract_address}:{token_id}'
    }
    if continuation:
        params['continuation'] = continuation
        
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        return data['sales'], data.get('continuation')
    else:
        print(f"Error: {response.status_code}")
        return None, None


def parse_nft_data(metadata, nft_price=None):
    """Extract relevant information from the NFT metadata"""
    parsed_data = {
        'name': metadata.get('name'),
        'owner': metadata.get('owner_of'),
        'image': eval(metadata.get('metadata', '{}')).get('image'),
        'token_id': metadata.get('token_id'),
        'token_address': metadata.get('token_address'),
        'metadata': {
            'symbol': metadata.get('symbol'),
            'rarity_rank': metadata.get('rarity_rank'),
            'rarity_percentage': metadata.get('rarity_percentage'),
            'amount': metadata.get('amount'),
        },
        'sales_history': metadata.get('sales_history', [])  # Use the sales history from metadata
    }
    return parsed_data




# Initialize Moralis
MORALIS_API_KEY = os.getenv('MORALIS_API')
# or alternatively:
# MORALIS_API_KEY = os.environ.get('K_SERVICE') and json.loads(os.environ.get('FIREBASE_CONFIG')).get('moralis', {}).get('api_key')

if not MORALIS_API_KEY:
    raise ValueError("Moralis API key not found in environment variables")

evm_api.api_key = MORALIS_API_KEY

# Replace the cloud function with a Flask route
@app.route('/get_nft_data', methods=['GET'])
def get_nft_data():
    # Get parameters from URL query parameters
    contract_address = request.args.get('contract_address')
    token_id = request.args.get('token_id')
    
    if not contract_address or not token_id:
        return jsonify({'error': 'Missing contract_address or token_id'}), 400

    try:
        result = main(contract_address, token_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
# Example usage

# Add this at the end of the file
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8081)))



