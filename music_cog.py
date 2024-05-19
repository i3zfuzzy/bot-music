import discord
import asyncio
from discord.ext import commands
from yt_dlp import YoutubeDL


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Variáveis de controle
        self.is_playing = False
        self.is_paused = False
        self.music_queue = asyncio.Queue()
        self.YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'False', 'default_search': 'auto'}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                               'options': '-vn'}

        self.vc = None

    async def play_music(self, ctx):
        while True:
            # Obter a próxima música da fila
            song = await self.music_queue.get()
            if song is None:
                # Se a música for None, significa que a fila está vazia
                self.is_playing = False
                await self.disconnect_if_inactive(ctx)
                return

            # Conectar ao canal de voz
            if self.vc is None or not self.vc.is_connected():
                self.vc = await song["channel"].connect()
            else:
                await self.vc.move_to(song["channel"])

            # Tocar a música
            self.vc.play(discord.FFmpegOpusAudio(song["source"], **self.FFMPEG_OPTIONS))

            # Aguardar até a música terminar de tocar
            while self.vc.is_playing():
                await asyncio.sleep(1)

            # Tocar a próxima música da fila
            await self.play_next(ctx)

    async def play_next(self, ctx):
        # Verificar se há mais músicas na fila
        if not self.music_queue.empty():
            await self.play_music(ctx)

    def search_yt(self, item):
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(item, download=False)
                if 'entries' in info:
                    # Se for uma lista de reprodução, retorna todas as músicas da lista
                    if 'webpage_url' in info:
                        return info['entries']
                    # Se for uma pesquisa, retorna apenas o primeiro resultado
                    else:
                        return [info['entries'][0]]
                else:
                    return [info]
            except Exception:
                return []

    async def disconnect_if_inactive(self, ctx):
        await asyncio.sleep(180)  # Espera 3 minutos (180 segundos)
        if not self.is_playing and not self.is_paused and (self.vc is None or not self.vc.is_playing()):
            await self.vc.disconnect()
            self.vc = None
            await ctx.send("Desconectado devido à inatividade.")

    @commands.command(name="play", aliases=["p", "playing"], help="Plays a selected song or playlist from YouTube")
    async def play(self, ctx, *args):
        query = " ".join(args)

        voice_channel = ctx.author.voice.channel
        if voice_channel is None:
            await ctx.send("Você precisa estar conectado a um canal de voz!")
            return

        songs = self.search_yt(query)
        if not songs:
            await ctx.send("Não foi possível encontrar a música ou a playlist.")
            return

        # Adicionar músicas à fila
        for song in songs:
            await self.music_queue.put({"source": song["url"], "channel": voice_channel})

        # Se não estiver tocando nada, iniciar a reprodução
        if not self.is_playing:
            self.is_playing = True
            await self.play_music(ctx)

    @commands.command(name="skip", help="Skips the current song being played")
    async def skip(self, ctx):
        if self.vc is not None and self.vc.is_playing():
            self.vc.stop()

    @commands.command(name="pause", help="Pauses the current song being played")
    async def pause(self, ctx):
        if self.vc and self.vc.is_playing():
            self.is_paused = True
            self.vc.pause()
            await ctx.send("Música pausada.")

    @commands.command(name="resume", help="Resumes the paused song")
    async def resume(self, ctx):
        if self.vc and self.is_paused:
            self.is_paused = False
            self.vc.resume()
            await ctx.send("Música retomada.")

    @commands.command(name="queue", aliases=["q"], help="Displays the current songs in queue")
    async def queue(self, ctx):
        if self.current_playlist:
            queue_list = "\n".join(song['title'] for song in self.current_playlist)
            await ctx.send(f"Lista de reprodução atual:\n{queue_list}")
        else:
            await ctx.send("Não há músicas na lista de reprodução.")

    # Limpar a fila de reprodução
    @commands.command(name="clear", aliases=["c", "bin"], help="Stops the music and clears the queue")
    async def clear(self, ctx):
        if self.vc is not None and self.vc.is_playing():
            self.vc.stop()
        self.music_queue = asyncio.Queue()
        await ctx.send("Fila limpa")

    @commands.command(name="leave", help="Makes the bot leave the voice channel")
    async def leave(self, ctx):
        if self.vc:
            await self.vc.disconnect()
            self.vc = None
            self.is_playing = False
            self.is_paused = False
            self.current_playlist = []
            await ctx.send("Bot desconectado.")


# Inicializa o cog
def setup(bot):
    bot.add_cog(MusicCog(bot))
