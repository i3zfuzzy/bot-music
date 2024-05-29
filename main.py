import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from help_cog import help_cog
from music_cog import MusicCog

load_dotenv()
TOKEN = os.getenv('discord_token')

intents = discord.Intents.all()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Remove o comando padrão help
bot.remove_command('help')

# Registra a classe com o bot
@bot.event
async def on_ready():
    await bot.add_cog(help_cog(bot))
    await bot.add_cog(MusicCog(bot))

@bot.command()
async def invite(ctx):
    """
    Retorna o link de convite do bot.
    """
    # Adicione os escopos e permissões conforme necessário
    scopes = ['bot']
    permissions = discord.Permissions(send_messages=True)
    url = discord.utils.oauth_url(bot.user.id, permissions=permissions, scopes=scopes)
    await ctx.send(f"Use este link para adicionar o bot ao seu servidor: {url}")

# Start do bot
bot.run(TOKEN)
