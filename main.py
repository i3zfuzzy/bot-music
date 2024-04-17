import discord
from discord.ext import commands
import os
# import all of the cogs
from dotenv import load_dotenv
from help_cog import help_cog
from music_cog import music_cog

load_dotenv()
TOKEN = os.getenv('discord_token')

intents = discord.Intents.all()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# remove o comando padrão help

bot.remove_command('help')


# registra a classe com o bot
@bot.event
async def on_ready():
    await bot.add_cog(help_cog(bot))
    await bot.add_cog(music_cog(bot))


# start do bot
bot.run(TOKEN)
