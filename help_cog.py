import discord
from discord.ext import commands

class help_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_message = """
```
General commands:
!help - Mostra todos os comandos
!p <keywords> - busca no youtube a musica e toca no canal que esta conectado, também da resume na musica que estava tocando.
!q - Mostra a fila de musicas
!skip - pula a música que esta tocando
!clear - para de tocar, e limpa a fila
!leave - desconecta do canal
!pause - pausa a música, ou volta a tocar, se estiver pausado
!resume - volta a tocar a música pausada
```
"""
        self.text_channel_list = []

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                self.text_channel_list.append(channel)

        await self.send_to_all(self.help_message)        

    @commands.command(name="help", help="Mostra todos os comandos disponíveis")
    async def help(self, ctx):
        await ctx.send(self.help_message)

    async def send_to_all(self, msg):
        for text_channel in self.text_channel_list:
            await text_channel.send(msg)