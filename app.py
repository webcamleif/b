import discord
import json
import os
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot_secret = os.getenv('BOT_SECRET')

# Dictionary to keep track of the channels
channels = {
    'monitor': None,
    'text': None
}

READY_EMOJI = '✅'  # Define the emoji you want to use for readying up

lobby_users = {}  # A dictionary to keep track of the users in the lobby
lobby_message_id = Nonelobby_message_id = None

def save_channels():
    with open('channels.json', 'w') as f:
        # Save only the channel IDs
        json.dump({k: v.id if v else None for k, v in channels.items()}, f)

def load_channels():
    try:
        with open('channels.json', 'r') as f:
            channel_ids = json.load(f)
            channels['monitor'] = bot.get_channel(channel_ids['monitor'])
            channels['text'] = bot.get_channel(channel_ids['text'])
    except FileNotFoundError:
        print("Channels file not found, skipping load.")

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel == channels['monitor']:
        # User joins the monitored channel
        lobby_users[member.id] = False  # Add user with a "NOT READY" status
        await update_lobby_status()

    if before.channel == channels['monitor'] and after.channel != channels['monitor']:
        # User leaves the monitored channel
        lobby_users.pop(member.id, None)  # Remove user from the lobby
        if lobby_message_id:  # If a lobby message exists
            try:
                lobby_message = await channels['text'].fetch_message(lobby_message_id)
                # Loop through the reactions on the message to find the READY_EMOJI
                for reaction in lobby_message.reactions:
                    if str(reaction.emoji) == READY_EMOJI:
                        async for user in reaction.users():  # Asynchronously iterate through the users
                            if user == member:
                                await reaction.remove(member)  # Remove the reaction
                                break
            except discord.NotFound:
                print("Lobby message not found when trying to remove reaction.")
            except discord.HTTPException as e:
                print(f"Failed to remove reaction: {e}")
        # Update the lobby status message
        await update_lobby_status()

async def update_lobby_status():
    if channels['text'] and channels['monitor']:
        global lobby_message_id
        message_content = "**CS2 Lobby Status**\n\n"

        # Get the current members in the monitored voice channel
        current_members = [member.id for member in channels['monitor'].members]
        # Filter the lobby_users dictionary to only include current members
        current_lobby_users = {member_id: status for member_id, status in lobby_users.items() if member_id in current_members}

        # Use the filtered dictionary for the count and player list
        message_content += f"**{len(current_lobby_users)} user(s) in lobby, need at least 6 users**\n"
        message_content += f"React with {READY_EMOJI} below to ready up\n\n"

        player_lines = []
        for member_id, status in current_lobby_users.items():
            member = channels['monitor'].guild.get_member(member_id)
            status_text = "READY" if status else "NOT READY"
            player_lines.append(f"{member.display_name} - {status_text}")

        player_list = "\n".join(player_lines)
        message_content += f"```yaml\nPlayers:\n{player_list}\n```"
        if lobby_message_id:  # If a message already exists, edit it
            try:
                lobby_message = await channels['text'].fetch_message(lobby_message_id)
                await lobby_message.edit(content=message_content)
            except discord.NotFound:
                lobby_message_id = None  # Reset if the message is not found
        if lobby_message_id is None:  # If no message exists or was not found, send a new one
            lobby_message = await channels['text'].send(message_content)
            lobby_message_id = lobby_message.id
            save_lobby_message_id()  # Save the new message ID
            await lobby_message.add_reaction(READY_EMOJI)
    else:
        print("Text channel not set.")

def save_lobby_message_id():
    with open('lobby_message_id.txt', 'w') as f:
        f.write(str(lobby_message_id))

def load_lobby_message_id():
    global lobby_message_id
    try:
        with open('lobby_message_id.txt', 'r') as f:
            lobby_message_id = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        lobby_message_id = None

@bot.event
async def on_reaction_add(reaction, user):
    print("Reaction added detected")  # Debugging print
    if user == bot.user or reaction.message.channel != channels['text']:
        return

    print(f"Reaction: {reaction.emoji}, User: {user.display_name}")  # Debugging print
    if str(reaction.emoji) == READY_EMOJI and user.id in lobby_users:
        lobby_users[user.id] = True
        await update_lobby_status()

@bot.event
async def on_reaction_remove(reaction, user):
    print("Reaction removed detected")  # Debugging print
    try:
        if user == bot.user or reaction.message.channel != channels['text']:
            return
    except Exception as e:
        print(f"Error in on_reaction_add: {e}")

    print(f"Reaction: {reaction.emoji}, User: {user.display_name}")  # Debugging print
    if str(reaction.emoji) == READY_EMOJI and user.id in lobby_users:
        lobby_users[user.id] = False
        await update_lobby_status()

@bot.event
async def on_ready():
    print(f"Intents: {bot.intents}")
    global lobby_message_id
    load_channels()  # Load channel IDs from the saved file
    load_lobby_message_id()  # Load the lobby message ID from the saved file
    if channels['text']:
        # If we have a saved message ID, try to fetch the message
        if lobby_message_id:
            try:
                lobby_message = await channels['text'].fetch_message(lobby_message_id)
                await lobby_message.clear_reactions()
                await lobby_message.add_reaction(READY_EMOJI)
            except discord.NotFound:
                # If the message cannot be found, reset the ID and send a new message
                print("Lobby message not found, creating a new one.")
                lobby_message_id = None
                save_lobby_message_id()
                await update_lobby_status()  # This will create a new lobby message
            except discord.HTTPException as e:
                # If there's a different HTTP exception, log it
                print(f"Failed to fetch lobby message: {e}")
    else:
        print("Text channel not set or not found.")

    print(f'Logged in as {bot.user.name}')

@bot.command(name='cs_mon_channel')
async def cs_mon_channel(ctx, channel_name: str):
    # Find channel by name
    channel = discord.utils.get(ctx.guild.channels, name=channel_name)
    if channel:
        # Set the monitor channel
        channels['monitor'] = channel
        await ctx.send(f'CS monitoring channel set to: {channel.name}')
        save_channels()
    else:
        await ctx.send('Channel not found.')

@bot.command(name='cs_text_channel')
async def cs_text_channel(ctx, channel_name: str):
    # Find channel by name
    channel = discord.utils.get(ctx.guild.channels, name=channel_name)
    if channel:
        # Set the text channel
        channels['text'] = channel
        await ctx.send(f'CS text channel set to: {channel.name}')
        save_channels()
    else:
        await ctx.send('Channel not found.')

# The rest of your bot's logic and commands would go here

# Replace 'your_token_here' with your actual bot token
bot.run(bot_secret)
