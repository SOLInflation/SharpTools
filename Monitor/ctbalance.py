import time
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed
import datetime
import pytz
import json
import os

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

def get_balance(wallet_address, settings):
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [wallet_address]
    }
    
    backoff_time = 1  # Start with 1 second backoff
    max_retries = 5   # Maximum number of retries
    max_backoff_time = 60  # Maximum backoff time in seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.post(settings['solana_rpc_url'], json=payload, headers=headers)
            
            # Check if response is valid
            if not response.ok:
                print(f"HTTP Error: {response.status_code} - {response.text}")
                if attempt < max_retries - 1:
                    wait_time = min(backoff_time * (2 ** attempt), max_backoff_time)
                    print(f"Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                return 0.0
            
            # Try to parse JSON response
            try:
                result = response.json()
            except ValueError as e:
                print(f"Error parsing JSON response: {response.text[:100]}...")
                if attempt < max_retries - 1:
                    continue
                return 0.0
            
            if 'result' in result and 'value' in result['result']:
                balance_in_sol = result['result']['value'] / 1_000_000_000
                return balance_in_sol
            elif 'error' in result and result['error']['code'] == 429:
                if attempt < max_retries - 1:
                    wait_time = min(backoff_time * (2 ** attempt), max_backoff_time)
                    print(f"Rate limit exceeded. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
            else:
                print(f"Error: Unexpected response format: {result}")
                if attempt < max_retries - 1:
                    continue
                return 0.0
                
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = min(backoff_time * (2 ** attempt), max_backoff_time)
                print(f"Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            return 0.0
    
    print("Max retries reached. Returning 0 balance.")
    return 0.0

def get_wsol_balance(wallet_address):
    settings = load_settings()
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet_address,
            {"mint": "So11111111111111111111111111111111111111112"},  # WSOL mint address
            {"encoding": "jsonParsed"}
        ]
    }
    
    backoff_time = 1  # Start with 1 second backoff
    max_retries = 5   # Maximum number of retries
    max_backoff_time = 60  # Maximum backoff time

    for attempt in range(max_retries):
        try:
            response = requests.post(settings['solana_rpc_url'], json=payload, headers=headers)
            
            # Check if response is valid
            if not response.ok:
                print(f"HTTP Error: {response.status_code} - {response.text}")
                if attempt < max_retries - 1:
                    wait_time = min(backoff_time * (2 ** attempt), max_backoff_time)
                    print(f"Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                return 0.0
            
            # Try to parse JSON response
            try:
                result = response.json()
            except ValueError:
                print(f"Error parsing JSON response: {response.text[:100]}...")
                if attempt < max_retries - 1:
                    continue
                return 0.0

            if 'result' in result and 'value' in result['result']:
                accounts = result['result']['value']
                if accounts:
                    balance_in_wsol = int(accounts[0]['account']['data']['parsed']['info']['tokenAmount']['amount']) / 1_000_000_000
                    return balance_in_wsol
                return 0.0
            elif 'error' in result and result['error']['code'] == 429:
                wait_time = min(backoff_time * (2 ** attempt), max_backoff_time)
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print(f"Error: Unexpected response format: {result}")
                if attempt < max_retries - 1:
                    continue
                return 0.0
                
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = min(backoff_time * (2 ** attempt), max_backoff_time)
                print(f"Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            return 0.0
    
    print("Max retries reached. Returning 0 balance.")
    return 0.0

def get_usdc_balance(wallet_address):
    settings = load_settings()
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet_address,
            {"mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"},  # USDC mint address
            {"encoding": "jsonParsed"}
        ]
    }
    response = requests.post(settings['solana_rpc_url'], json=payload, headers=headers)
    
    try:
        result = response.json()
    except ValueError:
        print("Error: Unable to parse JSON response.")
        return 0.0

    if 'result' in result and 'value' in result['result']:
        accounts = result['result']['value']
        if accounts:
            # Assuming the first account is the USDC account
            balance_in_usdc = int(accounts[0]['account']['data']['parsed']['info']['tokenAmount']['amount']) / 1_000_000
        else:
            balance_in_usdc = 0.0
    else:
        print("Error: Unexpected response format or no USDC accounts found.")
        balance_in_usdc = 0.0

    return balance_in_usdc

def get_solana_price():
    """Get current Solana price in USD from CoinGecko"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "solana",
            "vs_currencies": "usd"
        }
        response = requests.get(url, params=params)
        data = response.json()
        return data["solana"]["usd"]
    except Exception as e:
        print(f"Error fetching Solana price: {e}")
        return None

def send_discord_alert(sol_balance, wsol_balance, daily_pnl):
    """Send low balance alert with USD values"""
    settings = load_settings()
    total_balance = sol_balance + wsol_balance
    
    # Get Solana price
    sol_price = get_solana_price()
    
    # Calculate USD values
    if sol_price:
        total_usd = total_balance * sol_price
        daily_pnl_usd = daily_pnl * sol_price
    else:
        sol_price = 0
        total_usd = 0
        daily_pnl_usd = 0
    
    embed = DiscordEmbed(title="⚠️ Low Balance Alert", color='ff0000')
    embed.set_description(f"<@{settings['discord_id']}> Warning: Balance is below threshold!")
    
    embed.add_embed_field(
        name="SOL", 
        value=f"{sol_balance:.2f} SOL\n(${sol_balance * sol_price:,.2f})", 
        inline=True
    )
    embed.add_embed_field(
        name="WSOL", 
        value=f"{wsol_balance:.2f} SOL\n(${wsol_balance * sol_price:,.2f})", 
        inline=True
    )
    embed.add_embed_field(
        name="Total", 
        value=f"{total_balance:.2f} SOL\n(${total_usd:,.2f})", 
        inline=False
    )
    embed.add_embed_field(
        name="Daily PnL", 
        value=f"{daily_pnl:+.2f} SOL\n(${daily_pnl_usd:+,.2f})", 
        inline=False
    )
    
    # Add SOL price
    embed.add_embed_field(name="SOL Price", value=f"${sol_price:,.2f}", inline=False)
    
    webhook = DiscordWebhook(url=settings['balance_10min_webhook'])
    webhook.add_embed(embed)
    webhook.execute()

def send_discord_balance_and_pnl(sol_balance, wsol_balance, vault_sol_balance, vault_usdc_balance, daily_pnl):
    """Send balance update to Discord with daily PnL and USD values"""
    settings = load_settings()
    
    # Get Solana price
    sol_price = get_solana_price() or 0
    
    # Calculate totals
    bot_total_sol = sol_balance + wsol_balance
    bot_total_usd = bot_total_sol * sol_price
    vault_total_usd = (vault_sol_balance * sol_price) + vault_usdc_balance
    combined_total_sol = bot_total_sol + vault_sol_balance
    combined_total_usd = bot_total_usd + vault_total_usd
    
    # Set color based on daily PnL
    color = '00ff00' if daily_pnl >= 0 else 'ff0000'
    
    embed = DiscordEmbed(title="Balance and PnL Update", color=color)
    
    # Bot Wallet Section
    embed.add_embed_field(
        name="BOT WALLET",
        value=f"SOL: {sol_balance:.2f} (${sol_balance * sol_price:,.2f})\n"
              f"WSOL: {wsol_balance:.2f} (${wsol_balance * sol_price:,.2f})\n"
              f"Total Value: ${bot_total_usd:,.2f}",
        inline=False
    )
    
    # Vault Wallet Section
    embed.add_embed_field(
        name="VAULT WALLET",
        value=f"SOL: {vault_sol_balance:.2f} (${vault_sol_balance * sol_price:,.2f})\n"
              f"USDC: {vault_usdc_balance:.2f}\n"
              f"Total Value: ${vault_total_usd:,.2f}",
        inline=False
    )
    
    # Combined Section
    embed.add_embed_field(
        name="COMBINED",
        value=f"Total SOL: {combined_total_sol:.2f}\n"
              f"Total Value: ${combined_total_usd:,.2f}",
        inline=False
    )
    
    # SOL Price
    embed.add_embed_field(
        name="SOL PRICE",
        value=f"${sol_price:,.2f}",
        inline=False
    )
    
    # Add timestamp
    current_time = datetime.datetime.now(pytz.UTC)
    embed.set_footer(text=f"Updated at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    webhook = DiscordWebhook(url=settings['balance_10min_webhook'])
    webhook.add_embed(embed)
    webhook.execute()

def send_daily_balance_and_pnl(sol_balance, wsol_balance, total_pnl):
    settings = load_settings()
    total_balance = sol_balance + wsol_balance
    embed = DiscordEmbed(title="Daily Balance and PnL Update", color='03b2f8')
    embed.add_embed_field(name="SOL", value=f"{sol_balance} SOL", inline=True)
    embed.add_embed_field(name="WSOL", value=f"{wsol_balance} WSOL", inline=True)
    embed.add_embed_field(name="Total Balance", value=f"{total_balance} SOL", inline=False)
    embed.add_embed_field(name="12h Realized PnL", value=f"{total_pnl} SOL", inline=False)
    webhook = DiscordWebhook(url=settings['balance_daily_webhook'])
    webhook.add_embed(embed)
    webhook.execute()

class DailyPnLTracker:
    def __init__(self):
        self.reset_time = None
        self.starting_balance = None
        self.trades = []
        
    def update(self, current_total):
        current_time = datetime.datetime.now(pytz.UTC)
        
        # Reset at midnight UTC
        if (self.reset_time is None or 
            current_time.date() > self.reset_time.date()):
            self.reset_time = current_time
            self.starting_balance = current_total
            self.trades = []
            print(f"Daily PnL tracker reset. Starting balance: {self.starting_balance:.2f} SOL")
            
        # Record the current balance
        self.trades.append({
            'timestamp': current_time,
            'balance': current_total
        })
        
    def get_daily_pnl(self):
        if not self.starting_balance:
            return 0.0
        
        if not self.trades:
            return 0.0
            
        current_balance = self.trades[-1]['balance']
        daily_pnl = current_balance - self.starting_balance
        return daily_pnl

def monitor_balance():
    """Main balance monitoring function"""
    settings = load_settings()
    if not settings:
        print("Failed to load settings. Exiting...")
        return

    print("\nStarting balance monitoring...")
    
    # Initialize PnL tracker
    pnl_tracker = DailyPnLTracker()
    
    # Get wallet addresses from settings
    active_wallet_address = settings.get('botting_address')
    vault_wallet_address = settings.get('vault_address')
    
    if not active_wallet_address or not vault_wallet_address:
        print("Error: Missing wallet addresses in settings")
        return

    last_update_time = None  # Add this line to track last webhook send

    while True:
        try:
            # Get SOL balances
            print("\n=== Fetching New Balances ===")
            print("Fetching Active Wallet SOL...")
            active_sol = get_balance(active_wallet_address, settings)
            time.sleep(2)
            
            print("Fetching Active Wallet WSOL...")
            active_wsol = get_wsol_balance(active_wallet_address)
            time.sleep(2)
            
            print("Fetching Vault Wallet SOL...")
            vault_sol = get_balance(vault_wallet_address, settings)
            time.sleep(2)
            
            print("Fetching Vault Wallet USDC...")
            vault_usdc = get_usdc_balance(vault_wallet_address)
            
            # Calculate total balance (including vault)
            total_balance = active_sol + active_wsol + vault_sol
            
            # Update PnL tracker
            pnl_tracker.update(total_balance)
            daily_pnl = pnl_tracker.get_daily_pnl()
            
            # Low balance alert (if below threshold)
            if total_balance < settings.get('your_balance_threshold', 0):
                print("Sending low balance alert...")  # Add debug print
                send_discord_alert(active_sol, active_wsol, daily_pnl)
            
            # Regular update every 10 minutes
            current_time = datetime.datetime.now()
            if last_update_time is None or (current_time - last_update_time).seconds >= 600:  # 600 seconds = 10 minutes
                print("Sending regular balance update...")  # Add debug print
                send_discord_balance_and_pnl(active_sol, active_wsol, vault_sol, vault_usdc, daily_pnl)
                last_update_time = current_time
            
            # Print current balances
            print("\n=== Current Balances ===")
            print(f"Active Wallet:")
            print(f"  SOL:  {active_sol:.2f}")
            print(f"  WSOL: {active_wsol:.2f}")
            print(f"Vault Wallet:")
            print(f"  SOL:  {vault_sol:.2f}")
            print(f"  USDC: {vault_usdc:.2f}")
            print(f"Total Balance: {total_balance:.2f} SOL")
            print(f"Daily PnL: {daily_pnl:+.2f} SOL")
            
            time.sleep(20)  # Main loop delay
            
        except Exception as e:
            print(f"Error in monitor_balance: {str(e)}")
            time.sleep(30)  # Wait before retrying on error
            continue

if __name__ == "__main__":
    monitor_balance()
