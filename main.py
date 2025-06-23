import discord
from discord.ext import commands
import os
import time
from dotenv import load_dotenv
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
    start = time.time()
    print("Bot iniciando...")
    await bot.add_cog(help_cog(bot))
    await bot.add_cog(MusicCog(bot))
    print(f"Bot pronto em {time.time() - start:.2f} segundos")

@bot.command()
async def invite(ctx):
    """
    Retorna o link de convite do bot.
    """
    permissions = discord.Permissions(
        send_messages=True,
        manage_channels=True,
        manage_messages=True,
        connect=True,
        speak=True,
        use_external_emojis=True,
        use_application_commands=True
    )
    url = discord.utils.oauth_url(bot.user.id, permissions=permissions, scopes=['bot', 'applications.commands'])
    await ctx.send(f"Use este link para adicionar o bot ao seu servidor: {url}")

# Start do bot
bot.run(TOKEN)