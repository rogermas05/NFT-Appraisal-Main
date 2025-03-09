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
        "media_items": True,
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


# Example usage



