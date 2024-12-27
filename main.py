import threading
import sys
import os
import json
from Monitor import ctanalyser, ctbalance, ctcheck, bot
from colorama import init, Fore, Back, Style
import time

# Initialize colorama for cross-platform color support
init()

def clear_screen():
    """Clear the console screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_settings():
    """Load settings from settings.json"""
    try:
        settings_path = os.path.join(os.path.dirname(__file__), 'Monitor', 'settings.json')
        with open(settings_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading settings: {e}")
        return {}

def save_settings(settings):
    """Save settings to settings.json"""
    try:
        settings_path = os.path.join(os.path.dirname(__file__), 'Monitor', 'settings.json')
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def print_header(text):
    """Print a styled header"""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== {text} ==={Style.RESET_ALL}")

def print_success(text):
    """Print success message"""
    print(f"{Fore.GREEN}{text}{Style.RESET_ALL}")

def print_error(text):
    """Print error message"""
    print(f"{Fore.RED}{text}{Style.RESET_ALL}")

def print_warning(text):
    """Print warning message"""
    print(f"{Fore.YELLOW}{text}{Style.RESET_ALL}")

def edit_settings():
    """Edit settings with explanations"""
    settings = load_settings()
    if not settings:
        print_error("Failed to load settings.")
        return

    # Add missing fields that exist in settings.json but not in settings_info
    settings_info.update({
        "balance_10min_webhook": {
            "module": "Balance",
            "description": "Webhook URL for 10-minute balance updates"
        },
        "bot_token": {
            "module": "Bot",
            "description": "Discord bot token for authentication"
        },
        "sharp_webhook_channel_id": {
            "module": "Bot",
            "description": "Channel ID for Sharp webhook messages"
        },
        "bot_stats_channel_id": {
            "module": "Bot",
            "description": "Channel ID for bot statistics"
        }
    })

    while True:
        clear_screen()
        print_header("Settings Management")
        
        # Display settings by module with numbers
        setting_number = 1
        all_keys = []
        
        # Group settings by module - Add "Bot" to the modules dictionary
        modules = {"All": [], "Analyser": [], "Balance": [], "EmptyCheck": [], "Bot": []}
        for key in settings_info:
            module = settings_info[key]["module"]
            modules[module].append(key)

        # Display settings by module
        for module, keys in modules.items():
            if keys:
                print(f"\n{Fore.YELLOW}{Style.BRIGHT}{module} Module Settings:{Style.RESET_ALL}")
                for key in keys:
                    current_value = settings.get(key, "Not set")
                    # Handle different types of values
                    if isinstance(current_value, str):
                        if 'webhook' in key or 'token' in key:
                            display_value = f"{current_value[:30]}..." if current_value != "Not set" else "Not set"
                        else:
                            display_value = current_value
                    else:
                        display_value = str(current_value)
                    
                    print(f"{Fore.CYAN}{setting_number}. {key}:{Style.RESET_ALL} {display_value}")
                    print(f"   {Fore.WHITE}Description: {settings_info[key]['description']}{Style.RESET_ALL}")
                    all_keys.append(key)
                    setting_number += 1

        print(f"\n{Fore.GREEN}Options:{Style.RESET_ALL}")
        print(f"{setting_number}. Reset All Settings")
        print(f"{setting_number + 1}. Return to main menu")
        
        try:
            choice = input(f"\n{Fore.CYAN}Enter setting number to edit (1-{setting_number + 1}):{Style.RESET_ALL} ").strip()
            
            if choice.isdigit():
                choice_num = int(choice)
                if choice_num == setting_number + 1:  # Return to main menu
                    break
                elif choice_num == setting_number:  # Reset all settings
                    confirm = input(f"{Fore.RED}Are you sure you want to reset all settings? This cannot be undone! (y/N):{Style.RESET_ALL} ").strip().lower()
                    if confirm == 'y':
                        # Create empty settings while preserving all existing keys
                        new_settings = {key: "" for key in settings.keys()}
                        if save_settings(new_settings):
                            print_success("All settings have been reset!")
                        else:
                            print_error("Failed to reset settings!")
                        input("Press Enter to continue...")
                    continue
                    
                if 1 <= choice_num < setting_number:
                    key = all_keys[choice_num - 1]
                    print(f"\n{Fore.YELLOW}Editing: {key}{Style.RESET_ALL}")
                    print(f"Description: {settings_info[key]['description']}")
                    print(f"Current value: {settings.get(key, 'Not set')}")
                    new_value = input(f"{Fore.CYAN}Enter new value (or press Enter to cancel):{Style.RESET_ALL} ").strip()
                    
                    if new_value:
                        if 'threshold' in key:
                            try:
                                new_value = float(new_value)
                            except ValueError:
                                print_error("Invalid number format")
                                input("Press Enter to continue...")
                                continue
                        
                        settings[key] = new_value
                        if save_settings(settings):
                            print_success("Setting updated successfully!")
                        else:
                            print_error("Failed to save settings!")
                        input("Press Enter to continue...")
                else:
                    print_error("Invalid setting number!")
                    input("Press Enter to continue...")
            else:
                print_error("Invalid input!")
                input("Press Enter to continue...")
                
        except ValueError:
            print_error("Invalid input!")
            input("Press Enter to continue...")

def run_analyser():
    """Run the CT Analyser module"""
    print("Starting CT Analyser...")
    try:
        ctanalyser.schedule_analysis()
    except Exception as e:
        print(f"Error in CT Analyser: {str(e)}")

def run_balance():
    """Run the CT Balance module"""
    print("Starting CT Balance Monitor...")
    try:
        ctbalance.monitor_balance()
    except Exception as e:
        print(f"Error in CT Balance Monitor: {str(e)}")

def run_check():
    """Run the CT Check module"""
    print("Starting CT Check...")
    try:
        ctcheck.monitor_wallets()
    except Exception as e:
        print(f"Error in CT Check: {str(e)}")

def run_discord_bot():
    """Run the Discord bot module"""
    print("Starting Discord Bot...")
    try:
        bot.bot.run(bot.settings.get('bot_token'))
    except Exception as e:
        print(f"Error in Discord Bot: {str(e)}")

def start_monitors():
    """Start all monitoring threads"""
    threads = []
    
    try:
        # Create threads for each module with names
        analyser_thread = threading.Thread(target=run_analyser, name="Analyser")
        balance_thread = threading.Thread(target=run_balance, name="Balance")
        check_thread = threading.Thread(target=run_check, name="Check")
        bot_thread = threading.Thread(target=run_discord_bot, name="Discord Bot")
        
        # Make threads daemon so they stop when main program exits
        analyser_thread.daemon = True
        balance_thread.daemon = True
        check_thread.daemon = True
        bot_thread.daemon = True
        
        # Start threads with error handling
        for thread in [analyser_thread, balance_thread, check_thread, bot_thread]:
            try:
                thread.start()
                print_success(f"Started {thread.name} successfully")
            except Exception as e:
                print_error(f"Failed to start {thread.name}: {str(e)}")
        
        threads.extend([analyser_thread, balance_thread, check_thread, bot_thread])
        
        # Monitor thread health
        def monitor_threads():
            while True:
                for thread in threads:
                    if not thread.is_alive():
                        print_warning(f"{thread.name} died, attempting restart...")
                        try:
                            new_thread = threading.Thread(target=thread._target, name=thread.name)
                            new_thread.daemon = True
                            new_thread.start()
                            threads[threads.index(thread)] = new_thread
                            print_success(f"Restarted {thread.name}")
                        except Exception as e:
                            print_error(f"Failed to restart {thread.name}: {str(e)}")
                time.sleep(30)  # Check every 30 seconds
        
        # Start thread monitor in background
        monitor_thread = threading.Thread(target=monitor_threads, daemon=True)
        monitor_thread.start()
        
    except Exception as e:
        print_error(f"Error in start_monitors: {str(e)}")
    
    return threads

def main_menu():
    """Display the main menu and handle user input"""
    module_status = {
        'analyser': {'running': False, 'thread': None},
        'balance': {'running': False, 'thread': None},
        'check': {'running': False, 'thread': None},
        'bot': {'running': False, 'thread': None}
    }
    
    while True:
        clear_screen()
        print_header("Sharp Tools")
        
        # Display module statuses
        print(f"\n{Fore.YELLOW}Module Status:{Style.RESET_ALL}")
        print(f"1. CT Analyser: {Fore.GREEN if module_status['analyser']['running'] else Fore.RED}" +
              f"{'Running' if module_status['analyser']['running'] else 'Stopped'}{Style.RESET_ALL}")
        print(f"2. Balance Monitor: {Fore.GREEN if module_status['balance']['running'] else Fore.RED}" +
              f"{'Running' if module_status['balance']['running'] else 'Stopped'}{Style.RESET_ALL}")
        print(f"3. Empty CT Check: {Fore.GREEN if module_status['check']['running'] else Fore.RED}" +
              f"{'Running' if module_status['check']['running'] else 'Stopped'}{Style.RESET_ALL}")
        print(f"4. Discord Bot: {Fore.GREEN if module_status['bot']['running'] else Fore.RED}" +
              f"{'Running' if module_status['bot']['running'] else 'Stopped'}{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}Options:{Style.RESET_ALL}")
        print("5. Start All Monitors")
        print("6. Edit Settings")
        print("7. Exit Program")
        
        choice = input(f"\n{Fore.CYAN}Enter your choice (1-7):{Style.RESET_ALL} ").strip()
        
        if choice == "1":
            if not module_status['analyser']['running']:
                print_success("\nStarting CT Analyser...")
                thread = threading.Thread(target=run_analyser)
                thread.daemon = True
                thread.start()
                module_status['analyser']['running'] = True
                module_status['analyser']['thread'] = thread
                print_success("CT Analyser is now running!")
            else:
                print_warning("\nCT Analyser is already running!")
            input("\nPress Enter to return to menu...")
            
        elif choice == "2":
            if not module_status['balance']['running']:
                print_success("\nStarting Balance Monitor...")
                thread = threading.Thread(target=run_balance)
                thread.daemon = True
                thread.start()
                module_status['balance']['running'] = True
                module_status['balance']['thread'] = thread
                print_success("Balance Monitor is now running!")
            else:
                print_warning("\nBalance Monitor is already running!")
            input("\nPress Enter to return to menu...")
            
        elif choice == "3":
            if not module_status['check']['running']:
                print_success("\nStarting Empty CT Check...")
                thread = threading.Thread(target=run_check)
                thread.daemon = True
                thread.start()
                module_status['check']['running'] = True
                module_status['check']['thread'] = thread
                print_success("Empty CT Check is now running!")
            else:
                print_warning("\nEmpty CT Check is already running!")
            input("\nPress Enter to return to menu...")
            
        elif choice == "4":
            if not module_status['bot']['running']:
                print_success("\nStarting Discord Bot...")
                thread = threading.Thread(target=run_discord_bot)
                thread.daemon = True
                thread.start()
                module_status['bot']['running'] = True
                module_status['bot']['thread'] = thread
                print_success("Discord Bot is now running!")
            else:
                print_warning("\nDiscord Bot is already running!")
            input("\nPress Enter to return to menu...")
            
        elif choice == "5":
            if not any(module['running'] for module in module_status.values()):
                print_success("\nStarting all monitors...")
                for module_name, run_func in [
                    ('analyser', run_analyser),
                    ('balance', run_balance),
                    ('check', run_check),
                    ('bot', run_discord_bot)
                ]:
                    thread = threading.Thread(target=run_func)
                    thread.daemon = True
                    thread.start()
                    module_status[module_name]['running'] = True
                    module_status[module_name]['thread'] = thread
                print_success("All monitors are now running!")
            else:
                print_warning("\nSome monitors are already running!")
            input("\nPress Enter to return to menu...")
                
        elif choice == "6":
            edit_settings()
            
        elif choice == "7":
            print_warning("\nShutting down all monitors...")
            sys.exit(0)
            
        else:
            print_error("\nInvalid choice. Please try again.")
            input("\nPress Enter to continue...")

# Add all settings fields with descriptions
settings_info = {
    "solana_rpc_url": {
        "module": "All",
        "description": "Solana RPC URL for blockchain interactions"
    },
    "botting_address": {
        "module": "All",
        "description": "Main botting wallet address"
    },
    "vault_address": {
        "module": "All",
        "description": "Vault wallet address"
    },
    "discord_id": {
        "module": "All",
        "description": "Discord user ID for notifications"
    },
    "analyser_csv_webhook": {
        "module": "Analyser",
        "description": "Webhook URL for CSV analysis reports"
    },
    "analyser_single_webhook": {
        "module": "Analyser",
        "description": "Webhook URL for single transaction analysis"
    },
    "balance_10min_webhook": {
        "module": "Balance",
        "description": "Webhook URL for 10-minute balance updates"
    },
    "balance_daily_webhook": {
        "module": "Balance",
        "description": "Webhook URL for daily balance reports"
    },
    "check_empty_ct_webhook": {
        "module": "EmptyCheck",
        "description": "Webhook URL for empty CT notifications"
    },
    "your_balance_threshold": {
        "module": "Balance",
        "description": "Threshold for your wallet balance alerts"
    },
    "target_balance_threshold": {
        "module": "Balance",
        "description": "Threshold for target wallet balance alerts"
    },
    "bot_token": {
        "module": "Bot",
        "description": "Discord bot token for authentication"
    },
    "sharp_webhook_channel_id": {
        "module": "Bot",
        "description": "Channel ID from your Sharp webhook"
    },
    "bot_stats_channel_id": {
        "module": "Bot",
        "description": "Channel ID for bot statistics"
    }
}

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nShutting down all monitors...")
        sys.exit(0)
