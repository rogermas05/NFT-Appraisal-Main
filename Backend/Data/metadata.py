from moralis import evm_api
from dotenv import load_dotenv
import os
import requests
from datetime import datetime

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


# Example usage
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

