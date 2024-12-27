import discord
from discord.ext import commands
import re
from statistics import mean, median
import asyncio
from datetime import datetime, timedelta
import pytz
import json
import os

def load_settings():
    """Load settings from settings.json"""
    try:
        settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        with open(settings_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading settings: {e}")
        return {}

settings = load_settings()

intents = discord.Intents.default()
intents.message_content = True
intents.guild_messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Store block differences
block_differences = []  # Will store tuples of (timestamp, difference)
MONITOR_CHANNEL_ID = settings.get('sharp_webhook_channel_id')  # Changed from sharp_webhook_channel_ids
STATS_CHANNEL_ID = settings.get('bot_stats_channel_id')

block_frequencies = {}

# Add this after other global variables
channel_block_counts = {MONITOR_CHANNEL_ID: 0}  # Simplified to single channel

last_update = datetime.now()

# Add these new variables after other global variables
current_stats_message_id = None
berlin_tz = pytz.timezone('Europe/Berlin')

# Add new global variables at the top with other globals
grpc_counts = {"In-House": 0, "Custom": 0}  # Track GRPC types

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
    # Add debug logging
    print(f'Monitoring channel ID: {MONITOR_CHANNEL_ID}')
    print(f'Stats channel ID: {STATS_CHANNEL_ID}')
    
    # Check if channels exist and bot has permissions
    monitor_channel = bot.get_channel(MONITOR_CHANNEL_ID)
    stats_channel = bot.get_channel(STATS_CHANNEL_ID)
    
    if not monitor_channel:
        print(f"ERROR: Could not find monitor channel with ID {MONITOR_CHANNEL_ID}")
        return
    if not stats_channel:
        print(f"ERROR: Could not find stats channel with ID {STATS_CHANNEL_ID}")
        return
        
    print(f"Found monitor channel: #{monitor_channel.name}")
    print(f"Found stats channel: #{stats_channel.name}")
    
    # Check permissions
    bot_member = monitor_channel.guild.get_member(bot.user.id)
    required_permissions = ['view_channel', 'send_messages', 'embed_links', 'read_message_history']
    
    for channel in [monitor_channel, stats_channel]:
        missing_perms = [perm for perm in required_permissions 
                        if not getattr(channel.permissions_for(bot_member), perm)]
        if missing_perms:
            print(f"ERROR: Missing permissions in #{channel.name}: {', '.join(missing_perms)}")
            return
    
    # If we get here, permissions look good
    print("Starting history scan...")
    await scan_channel_history(monitor_channel)

async def scan_channel_history(channel):
    print(f"Scanning history for #{channel.name}...")
    block_differences.clear()
    channel_block_counts[channel.id] = 0
    grpc_counts.clear()
    grpc_counts.update({"In-House": 0, "Custom": 0})
    
    twenty_four_hours_ago = datetime.now() - timedelta(days=1)
    message_count = 0
    
    try:
        async for message in channel.history(limit=None, after=twenty_four_hours_ago):
            message_count += 1
            if message.embeds:
                for embed in message.embeds:
                    for field in embed.fields:
                        if field.name == "Block Difference":
                            try:
                                number = int(re.search(r'\d+', field.value).group())
                                block_differences.append((message.created_at, number))
                                channel_block_counts[channel.id] += 1
                            except (AttributeError, ValueError) as e:
                                print(f"Error parsing block difference: {e}")
                                continue
                        elif field.name == "GRPC":
                            grpc_value = field.value.strip()
                            if grpc_value in ["In-House", "Custom"]:
                                grpc_counts[grpc_value] += 1
        
        print(f"Scan complete. Processed {message_count} messages.")
        print(f"Found {len(block_differences)} block differences")
        print(f"GRPC counts: {grpc_counts}")
        
        await update_average_display()
    except Exception as e:
        print(f"Error during history scan: {e}")

async def update_average_display():
    global last_update, update_queued, current_stats_message_id
    
    if not block_differences:
        return
    
    block_frequencies.clear()
    for _, diff in block_differences:
        block_frequencies[diff] = block_frequencies.get(diff, 0) + 1
    
    stats_channel = bot.get_channel(STATS_CHANNEL_ID)
    if stats_channel:
        current_time = datetime.now()
        berlin_time = datetime.now(berlin_tz)
        total_occurrences = sum(block_frequencies.values())
        
        # Check if it's time for a new message (same logic as before)
        should_create_new = False
        if current_stats_message_id is None:
            should_create_new = True
        else:
            if berlin_time.hour == 16 and berlin_time.minute >= 15:
                try:
                    old_message = await stats_channel.fetch_message(current_stats_message_id)
                    message_time = old_message.created_at.astimezone(berlin_tz)
                    if message_time.date() < berlin_time.date():
                        should_create_new = True
                except discord.NotFound:
                    should_create_new = True

        # Calculate statistics
        block_numbers = [diff for _, diff in block_differences]
        avg_blocks = round(mean(block_numbers), 2)
        median_blocks = round(median(block_numbers), 2)
        
        # Create embed
        embed = discord.Embed(
            title="📊 Block Difference Statistics",
            color=discord.Color.blue(),
            timestamp=current_time
        )
        
        # Add period information
        period_start = (current_time - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
        period_end = current_time.strftime('%Y-%m-%d %H:%M')
        embed.add_field(
            name="📅 Time Period",
            value=f"From {period_start}\nTo {period_end}",
            inline=False
        )
        
        # Add main statistics
        embed.add_field(
            name="📈 Key Metrics",
            value=f"Average: **{avg_blocks}** blocks\nMedian: **{median_blocks}** blocks",
            inline=False
        )
        
        # Add channel-specific counts
        channel = bot.get_channel(MONITOR_CHANNEL_ID)
        channel_name = channel.name if channel else f"Channel {MONITOR_CHANNEL_ID}"
        channel_count = channel_block_counts[MONITOR_CHANNEL_ID]
        channel_stats = f"#{channel_name}: **{channel_count}**\n"
        
        embed.add_field(
            name="📊 Channel Distribution",
            value=channel_stats,
            inline=False
        )
        
        # Add block frequency distribution
        frequency_stats = ""
        for diff in sorted(block_frequencies.keys()):
            percentage = (block_frequencies[diff] / total_occurrences) * 100
            frequency_stats += f"`{diff:2d}` blocks: **{block_frequencies[diff]}** times ({percentage:.2f}%)\n"
        
        embed.add_field(
            name="🔢 Block Difference Distribution",
            value=frequency_stats,
            inline=False
        )
        
        # Add GRPC distribution
        total_grpc = sum(grpc_counts.values())
        if total_grpc > 0:
            grpc_stats = ""
            for grpc_type, count in grpc_counts.items():
                percentage = (count / total_grpc * 100)
                grpc_stats += f"{grpc_type}: **{count}** ({percentage:.2f}%)\n"
            
            embed.add_field(
                name="🔧 GRPC Distribution",
                value=grpc_stats,
                inline=False
            )
        
        # Add footer
        embed.set_footer(text="Stats auto-update every 24 hours at 16:15 Berlin time")
        
        try:
            if should_create_new:
                new_message = await stats_channel.send(embed=embed)
                current_stats_message_id = new_message.id
            else:
                message = await stats_channel.fetch_message(current_stats_message_id)
                await message.edit(embed=embed)
        except discord.HTTPException as e:
            print(f"Error handling stats message: {e}")

@bot.event
async def on_message(message):
    if message.channel.id == MONITOR_CHANNEL_ID and message.embeds:  # Changed from 'in' to '=='
        for embed in message.embeds:
            for field in embed.fields:
                if field.name == "Block Difference":
                    try:
                        current_time = datetime.now()
                        twenty_four_hours_ago = current_time - timedelta(days=1)
                        
                        global block_differences
                        block_differences = [(time, diff) for time, diff in block_differences if time > twenty_four_hours_ago]
                        
                        number = int(re.search(r'\d+', field.value).group())
                        block_differences.append((current_time, number))
                        channel_block_counts[message.channel.id] += 1
                    except (AttributeError, ValueError):
                        continue
                
                # Check for GRPC
                elif field.name == "GRPC":
                    grpc_value = field.value.strip()
                    if grpc_value in ["In-House", "Custom"]:
                        grpc_counts[grpc_value] += 1
            
            # Update display after processing all fields
            await update_average_display()

    await bot.process_commands(message)