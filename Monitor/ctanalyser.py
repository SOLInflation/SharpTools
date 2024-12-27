import pandas as pd
import os
from discord_webhook import DiscordWebhook, DiscordEmbed
import datetime
import time
import numpy as np
import schedule
import pytz
from datetime import timedelta
import json

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

def load_all_sessions():
    """Load all available session CSV files"""
    # Get the path to the Sharp root directory (two levels up from the script)
    sharp_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    all_data = []
    
    # Define expected columns to ensure consistent DataFrame structure
    expected_columns = ['Date', 'Token', 'Action', 'Invested', 'Received', 'Target Wallet']
    
    for filename in os.listdir(sharp_root):
        if filename.startswith("ct-session-") and filename.endswith(".csv"):
            file_path = os.path.join(sharp_root, filename)
            try:
                df = pd.read_csv(file_path)
                # Ensure all expected columns exist and have proper types
                for col in expected_columns:
                    if col not in df.columns:
                        if col in ['Invested', 'Received']:
                            df[col] = 0.0  # Use 0.0 for numeric columns
                        else:
                            df[col] = ''  # Use empty string for other columns
                # Select only the expected columns in the specified order
                df = df[expected_columns]
                if not df.empty:  # Only append non-empty DataFrames
                    all_data.append(df)
            except Exception as e:
                print(f"Error reading file {filename}: {str(e)}")
    
    if not all_data:
        print("No session files found")
        # Return empty DataFrame with expected columns and proper dtypes
        return pd.DataFrame({
            'Date': pd.Series(dtype='datetime64[ns, UTC]'),
            'Token': pd.Series(dtype='str'),
            'Action': pd.Series(dtype='str'),
            'Invested': pd.Series(dtype='float64'),
            'Received': pd.Series(dtype='float64'),
            'Target Wallet': pd.Series(dtype='str')
        })
    
    # Concatenate with explicit dtype specifications
    combined_df = pd.concat(all_data, ignore_index=True, axis=0)
    
    # Convert Date column to datetime and ensure UTC timezone
    combined_df['Date'] = pd.to_datetime(combined_df['Date'], format='ISO8601', utc=True)
    
    # Ensure numeric columns are properly typed
    combined_df['Invested'] = pd.to_numeric(combined_df['Invested'], errors='coerce').fillna(0.0)
    combined_df['Received'] = pd.to_numeric(combined_df['Received'], errors='coerce').fillna(0.0)
    
    return combined_df

def filter_data_by_timeframe(df, hours=None, days=None):
    """Filter dataframe by specified timeframe"""
    if df.empty:
        return df
        
    now = pd.Timestamp.now(tz='UTC')
    if hours:
        start_time = now - pd.Timedelta(hours=hours)
    elif days:
        start_time = now - pd.Timedelta(days=days)
    else:
        return df  # Return all data if no timeframe specified
        
    return df[df['Date'] >= start_time]

def send_webhook_with_retry(webhook, max_retries=5):
    """Send webhook with retry logic for rate limits"""
    for attempt in range(max_retries):
        try:
            response = webhook.execute()
            if response and isinstance(response, list):
                response = response[0]  # Get first response if multiple
            
            # If successful, return
            if not response or response.status_code == 200:
                return
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = response.json().get('retry_after', 1)
                print(f"Rate limited, waiting {retry_after} seconds...")
                time.sleep(float(retry_after) + 0.1)  # Add small buffer
                continue
                
        except Exception as e:
            print(f"Webhook error: {str(e)}")
            time.sleep(1)
    
    print("Max retries reached for webhook")

def send_wallet_stats_to_discord(results_df, webhook_url, delay=1.5):
    """Send individual wallet stats as separate embeds"""
    if results_df.empty:
        print("No wallet results to send.")
        return

    # Process each wallet separately
    for _, row in results_df.iterrows():
        wallet = row['Target Wallet']
        
        # Create links
        gmgn_link = f"https://gmgn.ai/sol/address/{wallet}"
        cielo_link = f"https://app.cielo.finance/profile/{wallet}/pnl/tokens?timeframe=7d"
        
        # Set color based on total PNL
        color = 0x00ff00 if row['total_pnl'] > 0 else 0xff0000  # Green for positive, Red for negative
        
        embed = DiscordEmbed(
            title=f"{wallet}",  # Full wallet address as title
            description=(
                f"[GMGN]({gmgn_link}) | [CIELO]({cielo_link})\n\n"
                f"Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            color=color
        )
        
        # Add all stats fields
        embed.add_embed_field(name="Total Trades", value=str(row['total_trades']), inline=True)
        embed.add_embed_field(name="Win Rate", value=f"{row['win_rate']:.1f}%", inline=True)
        embed.add_embed_field(name="Average ROI", value=f"{row['avg_roi']:.1f}%", inline=True)
        embed.add_embed_field(name="Total PNL", value=f"{row['total_pnl']:.3f} SOL", inline=True)
        embed.add_embed_field(name="Total Invested", value=f"{row['Invested']:.3f} SOL", inline=True)
        embed.add_embed_field(name="Total Received", value=f"{row['Received']:.3f} SOL", inline=True)
        
        # Create new webhook for each wallet to send separate messages
        wallet_webhook = DiscordWebhook(url=webhook_url)
        wallet_webhook.add_embed(embed)
        
        # Use new retry logic
        send_webhook_with_retry(wallet_webhook)
        time.sleep(delay)  # Increased default delay between messages

def send_ranking_csv_to_discord(results_dict, webhook_url):
    """Send overall ranking as a CSV file with all timeframes"""
    if not results_dict:
        print("No results to send as CSV.")
        return
    
    # Get all unique wallets
    all_wallets = set()
    for df in results_dict.values():
        all_wallets.update(df['Target Wallet'].unique())
    
    # Create combined dataframe
    combined_data = []
    for wallet in all_wallets:
        wallet_data = {'Target_Wallet': wallet}
        
        # Add data for each timeframe
        for timeframe in ["All Time", "7 Days", "3 Days", "24 Hours", "12 Hours", "4 Hours"]:
            if timeframe in results_dict:
                df = results_dict[timeframe]
                wallet_df = df[df['Target Wallet'] == wallet]
                if not wallet_df.empty:
                    row = wallet_df.iloc[0]
                    prefix = timeframe.replace(' ', '_')
                    wallet_data.update({
                        f'{prefix}_trades': row['total_trades'],
                        f'{prefix}_win_rate': row['win_rate'],
                        f'{prefix}_roi': row['avg_roi'],
                        f'{prefix}_pnl': row['total_pnl'],
                        f'{prefix}_invested': row['Invested'],
                        f'{prefix}_received': row['Received']
                    })
                else:
                    # Fill with zeros if no data for this timeframe
                    prefix = timeframe.replace(' ', '_')
                    wallet_data.update({
                        f'{prefix}_trades': 0,
                        f'{prefix}_win_rate': 0,
                        f'{prefix}_roi': 0,
                        f'{prefix}_pnl': 0,
                        f'{prefix}_invested': 0,
                        f'{prefix}_received': 0
                    })
        
        combined_data.append(wallet_data)
    
    # Create DataFrame
    combined_df = pd.DataFrame(combined_data)
    
    # Sort by All Time PNL if available
    if 'All_Time_pnl' in combined_df.columns:
        combined_df = combined_df.sort_values('All_Time_pnl', ascending=False)
    
    # Save and send CSV
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f'wallet_ranking_all_timeframes_{timestamp}.csv'
    combined_df.to_csv(csv_filename, index=False)
    
    # Create webhook with CSV file
    webhook = DiscordWebhook(
        url=webhook_url,
        content=f"📈 Wallet Rankings - All Timeframes - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    with open(csv_filename, 'rb') as f:
        webhook.add_file(file=f.read(), filename=csv_filename)
    
    send_webhook_with_retry(webhook)
    
    # Clean up the file
    os.remove(csv_filename)

def analyze_trades(df):
    # Get first seen timestamp for each wallet
    first_seen = df.groupby('Target Wallet')['Date'].min().reset_index()
    first_seen = first_seen.rename(columns={'Date': 'first_seen'})
    
    # Group by wallet and token to get stats per token
    token_stats = df.groupby(['Target Wallet', 'Token']).agg({
        'Invested': lambda x: x[df['Action'] == 'Buy'].sum(),
        'Received': lambda x: x[df['Action'] == 'Sell'].sum()
    }).reset_index()
    
    # Calculate realized ROI for each token
    token_stats['ROI'] = ((token_stats['Received'] - token_stats['Invested']) / token_stats['Invested'] * 100)
    
    # Now group by wallet to get wallet statistics
    wallet_stats = token_stats.groupby('Target Wallet').agg({
        'Token': 'count',  # Number of tokens traded
        'Invested': 'sum',
        'Received': 'sum'
    }).reset_index()
    
    # Calculate realized ROI for the wallet (not average of token ROIs)
    wallet_stats['avg_roi'] = ((wallet_stats['Received'] - wallet_stats['Invested']) / wallet_stats['Invested'] * 100)
    
    # Calculate win rate (percentage of profitable tokens)
    win_rates = token_stats[token_stats['ROI'].notna()].groupby('Target Wallet').agg({
        'ROI': lambda x: (x > 0).mean() * 100  # Percentage of winning trades
    }).reset_index()
    win_rates = win_rates.rename(columns={'ROI': 'win_rate'})  # Rename before merge
    
    # Merge stats and calculate final metrics
    wallet_stats = wallet_stats.merge(win_rates, on='Target Wallet', how='left')
    wallet_stats['total_pnl'] = wallet_stats['Received'] - wallet_stats['Invested']
    
    # Fill NaN win rates with 0
    wallet_stats['win_rate'] = wallet_stats['win_rate'].fillna(0)
    
    # Rename columns for clarity
    wallet_stats = wallet_stats.rename(columns={
        'Token': 'total_trades'
    })
    
    # Merge first seen data
    wallet_stats = wallet_stats.merge(first_seen, on='Target Wallet', how='left')
    
    return wallet_stats.sort_values('total_pnl', ascending=False)

def send_timeframe_results_to_discord(df, webhook_url, timeframe_label):
    """Send results for a specific timeframe"""
    if df.empty:
        print(f"No results for {timeframe_label} timeframe")
        return

    webhook = DiscordWebhook(url=webhook_url)
    
    # Create main message
    main_embed = DiscordEmbed(
        title=f"📊 Wallet Performance - {timeframe_label}",
        description=f"Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        color=0x00ff00
    )
    webhook.add_embed(main_embed)
    webhook.execute()
    time.sleep(1)  # Prevent rate limiting

    # Send individual wallet stats
    for _, row in df.iterrows():
        send_wallet_stats_to_discord(pd.DataFrame([row]), webhook_url)
        time.sleep(1)  # Prevent rate limiting

def get_color_and_emoji_by_roi(roi):
    """Get color and emoji based on ROI performance"""
    if roi >= 20:
        return 0x00FF00, "💰"  # Bright green with money bag for excellent ROI (>20%)
    elif roi >= 5:
        return 0x90EE90, "🟢"  # Light green for good ROI (5-20%)
    elif roi >= -5:
        return 0xFFFFFF, "⚪"  # White for neutral ROI (-5 to +5%)
    elif roi >= -20:
        return 0xFFA500, "🟡"  # Orange for poor ROI (-20 to -5%)
    else:
        return 0xFF0000, "🔴"  # Red for very poor ROI (<-20%)

def get_timeframe_emoji(timeframe_label):
    """Get emoji for different timeframes"""
    timeframe_emojis = {
        "4 Hours": "⏰",
        "12 Hours": "⏱️",
        "24 Hours": "📅",
        "3 Days": "📆",
        "7 Days": "📊",
        "All Time": "🏆"
    }
    return timeframe_emojis.get(timeframe_label, "📈")

def send_combined_wallet_stats(results_dict, webhook_url, timeframe_type="All"):
    """Send combined timeframe stats for each wallet"""
    if not results_dict:
        print(f"No {timeframe_type} timeframe results to send.")
        return

    # Get unique wallets across all timeframes
    all_wallets = set()
    for df in results_dict.values():
        all_wallets.update(df['Target Wallet'].unique())

    # Process each wallet
    for wallet in all_wallets:
        # Get all-time ROI and first seen for overall webhook color
        all_time_roi = None
        first_seen = None
        if "All Time" in results_dict:
            wallet_data = results_dict["All Time"][results_dict["All Time"]['Target Wallet'] == wallet]
            if not wallet_data.empty:
                row = wallet_data.iloc[0]
                all_time_roi = row['avg_roi']
                first_seen = row.get('first_seen')
        
        # Create links
        gmgn_link = f"https://gmgn.ai/sol/address/{wallet}"
        cielo_link = f"https://app.cielo.finance/profile/{wallet}/pnl/tokens?timeframe=7d"
        
        # Shortened wallet address
        short_wallet = f"{wallet[:6]}...{wallet[-6:]}"
        
        # Get color based on all-time ROI
        main_color = 0x808080  # Default gray if no all-time data
        if all_time_roi is not None:
            main_color = get_color_and_emoji_by_roi(all_time_roi)[0]

        webhook = DiscordWebhook(url=webhook_url)
        
        main_embed = DiscordEmbed(
            title=f"📊 {short_wallet}",
            description=(
                f"[GMGN]({gmgn_link}) | [CIELO]({cielo_link})\n"
                f"First Seen: {format_relative_time(first_seen) if first_seen else 'Unknown'}\n"
                f"Updated: <t:{int(time.time())}:R>"
            ),
            color=main_color
        )
        webhook.add_embed(main_embed)

        # Add timeframe sections
        for timeframe_label, df in results_dict.items():
            wallet_data = df[df['Target Wallet'] == wallet]
            timeframe_emoji = get_timeframe_emoji(timeframe_label)
            
            if wallet_data.empty or wallet_data.iloc[0]['total_trades'] == 0:
                # Wallet didn't trade in this timeframe
                timeframe_embed = DiscordEmbed(
                    title=f"{timeframe_emoji} {timeframe_label}",
                    description="⚠️ **NOT TRADED**",
                    color=0x808080  # Gray color for inactive timeframes
                )
            else:
                # Wallet traded in this timeframe
                row = wallet_data.iloc[0]
                color, status_emoji = get_color_and_emoji_by_roi(row['avg_roi'])
                
                timeframe_embed = DiscordEmbed(
                    title=f"{timeframe_emoji} {timeframe_label}",
                    description=(
                        f"PNL: {row['total_pnl']:.3f} SOL\n"
                        f"Trades: {row['total_trades']}\n"
                        f"Win Rate: {row['win_rate']:.1f}%\n"
                        f"{status_emoji} **Avg ROI: {row['avg_roi']:.1f}%**\n"
                        f"Invested: {row['Invested']:.3f} SOL\n"
                        f"Received: {row['Received']:.3f} SOL"
                    ),
                    color=color
                )
            webhook.add_embed(timeframe_embed)

        # Send webhook with retry logic
        send_webhook_with_retry(webhook)
        time.sleep(1.5)  # Increased delay between wallets

def run_analysis():
    """Main function to run the analysis"""
    settings = load_settings()
    if not settings:
        print("Failed to load settings. Exiting...")
        return
        
    print(f"\n=== Starting analysis at {datetime.datetime.now(pytz.timezone('CET')).strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    # Load all session data
    df = load_all_sessions()
    if df.empty:
        print("No data found for analysis")
        return
    
    # Store all results in one dictionary
    all_timeframe_results = {}
    
    # Process short timeframes (4h, 12h, 24h)
    for hours, label in [(4, "4 Hours"), (12, "12 Hours"), (24, "24 Hours")]:
        filtered_df = filter_data_by_timeframe(df, hours=hours)
        results = analyze_trades(filtered_df)
        if not results.empty:
            all_timeframe_results[label] = results
    
    # Process long timeframes (3d, 7d)
    for days, label in [(3, "3 Days"), (7, "7 Days")]:
        filtered_df = filter_data_by_timeframe(df, days=days)
        results = analyze_trades(filtered_df)
        if not results.empty:
            all_timeframe_results[label] = results
    
    # Add all-time results
    all_time_results = analyze_trades(df)
    if not all_time_results.empty:
        all_timeframe_results["All Time"] = all_time_results
    
    # Send all timeframe results
    if all_timeframe_results:
        send_combined_wallet_stats(all_timeframe_results, settings['analyser_single_webhook'])
        send_ranking_csv_to_discord(all_timeframe_results, settings['analyser_csv_webhook'])

def schedule_analysis():
    """Schedule the analysis to run every 4 hours"""
    print("Analysis scheduler started. Will run every 4 hours at XX:00 CET")
    
    try:
        # Run immediately when started
        print("Running initial analysis...")
        run_analysis()
        print("Initial analysis completed.")
        
        # Schedule the job to run every 4 hours at XX:00
        schedule.every(4).hours.at(":00").do(run_analysis)
        print("Scheduler set up successfully. Entering main loop...")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
            
    except Exception as e:
        print(f"Error in scheduler: {str(e)}")
        print("Attempting to restart analysis...")
        time.sleep(5)  # Wait 5 seconds before trying again
        schedule_analysis()  # Recursive restart

def format_relative_time(timestamp):
    """Convert timestamp to Discord timestamp format"""
    # Convert timestamp to Unix timestamp (seconds since epoch)
    unix_timestamp = int(timestamp.timestamp())
    return f"<t:{unix_timestamp}:R>"

if __name__ == "__main__":
    try:
        schedule_analysis()
    except KeyboardInterrupt:
        print("\nShutting down scheduler...")
    except Exception as e:
        print(f"Error in main loop: {str(e)}")