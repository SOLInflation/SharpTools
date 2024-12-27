import time
import json
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed
from pathlib import Path
import os

# Constants that stay the same
EMPTY_FILE = "empty.txt"

def load_settings():
    """Load settings from settings.json"""
    try:
        settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        return settings
    except Exception as e:
        print(f"Error loading settings: {e}")
        return {}

def load_alerted_wallets():
    try:
        if Path(EMPTY_FILE).exists():
            with open(EMPTY_FILE, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    except Exception as e:
        print(f"Error loading alerted wallets: {e}")
        return set()

def save_alerted_wallet(wallet):
    try:
        with open(EMPTY_FILE, 'a') as f:
            f.write(f"{wallet}\n")
    except Exception as e:
        print(f"Error saving alerted wallet: {e}")

def get_sol_balance(wallet_address, settings):
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [wallet_address]
    }
    
    try:
        response = requests.post(settings['solana_rpc_url'], json=payload, headers=headers)
        result = response.json()
        if 'result' in result and 'value' in result['result']:
            return result['result']['value'] / 1_000_000_000
    except Exception as e:
        print(f"Error getting SOL balance: {e}")
    return 0.0

def get_wsol_balance(wallet_address, settings):
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet_address,
            {"mint": "So11111111111111111111111111111111111111112"},
            {"encoding": "jsonParsed"}
        ]
    }
    
    try:
        response = requests.post(settings['solana_rpc_url'], json=payload, headers=headers)
        result = response.json()
        if 'result' in result and 'value' in result['result']:
            accounts = result['result']['value']
            if accounts:
                return int(accounts[0]['account']['data']['parsed']['info']['tokenAmount']['amount']) / 1_000_000_000
    except Exception as e:
        print(f"Error getting WSOL balance: {e}")
    return 0.0

def send_alert(wallet_address, sol_balance, wsol_balance, settings):
    total_balance = sol_balance + wsol_balance
    embed = DiscordEmbed(title="⚠️ Low Balance Alert", color='ff0000')
    embed.add_embed_field(name="Wallet", value=wallet_address, inline=False)
    embed.add_embed_field(name="SOL", value=f"{sol_balance:.2f}", inline=True)
    embed.add_embed_field(name="WSOL", value=f"{wsol_balance:.2f}", inline=True)
    embed.add_embed_field(name="Total", value=f"{total_balance:.2f}", inline=True)
    embed.set_footer(text=f"Balance below {settings['target_balance_threshold']} SOL threshold")
    
    webhook = DiscordWebhook(
        url=settings['check_empty_ct_webhook'], 
        content=f"<@{settings['discord_id']}>"
    )
    webhook.add_embed(embed)
    webhook.execute()

def get_wallets_from_presets():
    wallets = set()  # Using set to avoid duplicates
    try:
        # Go up two directories from current file location to reach root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        preset_path = os.path.join(base_dir, 'config', 'preset', 'presets.json')
        
        print(f"Looking for presets.json at: {preset_path}")  # Debug line
        
        with open(preset_path, 'r') as f:
            data = json.load(f)
            
        # Check both sol_sniper and sol_copy_trade sections
        sections = ['sol_sniper', 'sol_copy_trade']
        for section in sections:
            if section in data:
                for entry in data[section]:
                    if 'task_input' in entry:
                        # Check all possible wallet keys (1-30)
                        for i in range(1, 31):
                            wallet_key = f'copy_trade_wallet{i}'
                            if wallet_key in entry['task_input']:
                                wallet = entry['task_input'][wallet_key]
                                if wallet and isinstance(wallet, str) and len(wallet) > 0:
                                    wallets.add(wallet)
        
        return list(wallets)
    except Exception as e:
        print(f"Error reading presets.json: {e}")
        return []

def monitor_wallets():
    settings = load_settings()
    if not settings:
        print("Failed to load settings. Exiting...")
        return
        
    alerted_wallets = load_alerted_wallets()
    
    while True:
        try:
            wallets = get_wallets_from_presets()
            print(f"\nMonitoring {len(wallets)} unique wallet addresses")
            print(f"Previously alerted wallets: {len(alerted_wallets)}")
            print("-" * 50)
            
            for wallet in wallets:
                if wallet in alerted_wallets:
                    continue
                    
                sol_balance = get_sol_balance(wallet, settings)
                time.sleep(0.2)
                wsol_balance = get_wsol_balance(wallet, settings)
                time.sleep(0.2)
                
                total_balance = sol_balance + wsol_balance
                print(f"Wallet: {wallet}")
                print(f"SOL: {sol_balance:.2f}")
                print(f"WSOL: {wsol_balance:.2f}")
                print(f"Total: {total_balance:.2f} SOL")
                print("-" * 50)
                
                if total_balance < settings['target_balance_threshold']:
                    send_alert(wallet, sol_balance, wsol_balance, settings)
                    save_alerted_wallet(wallet)
                    alerted_wallets.add(wallet)
                    time.sleep(1)
            
            time.sleep(15)
            
        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            time.sleep(15)

if __name__ == "__main__":
    monitor_wallets()
