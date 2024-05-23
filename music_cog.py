import discord
import asyncio
from discord.ext import commands
from yt_dlp import YoutubeDL
import textwrap

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Variáveis de controle
        self.is_playing = False
        self.is_paused = False
        self.music_queue = []
        self.current_song = None
        self.YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': False, 'default_search': 'auto', 'ignoreerrors': True, 'skip_download': True}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

        self.vc = None

    async def play_music(self, ctx):
        while self.music_queue:
            song = self.music_queue.pop(0)
            if song is None:
                self.is_playing = False
                await self.disconnect_if_inactive(ctx)
                return

            self.current_song = song  # Atualizar a música atual

            if self.vc is None or not self.vc.is_connected():
                try:
                    self.vc = await song["channel"].connect()
                except Exception as e:
                    print(f"Erro ao conectar ao canal de voz: {e}")
                    await ctx.send("Não foi possível conectar ao canal de voz.")
                    self.is_playing = False
                    return
            else:
                await self.vc.move_to(song["channel"])

            try:
                print(f"Tocando música: {song['title']}")
                source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(song["source"], **self.FFMPEG_OPTIONS))
                self.vc.play(source, after=lambda e: self.bot.loop.create_task(self.song_finished(ctx, e)))
                self.is_playing = True
                await ctx.send(f"Tocando agora: {song['title']}")
                while self.vc.is_playing() or self.is_paused:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Erro ao tentar tocar a música: {e}")
                await ctx.send("Erro ao tentar tocar a música.")
                continue

        await self.disconnect_if_inactive(ctx)

    async def song_finished(self, ctx, error):
        if error:
            print(f"Player error: {error}")
        if self.music_queue:
            await self.play_music(ctx)
        else:
            self.is_playing = False
            await self.disconnect_if_inactive(ctx)

    async def add_songs_to_queue(self, ctx, songs, voice_channel):
        for song in songs:
            if song is None or "url" not in song:
                continue
            self.music_queue.append({"source": song["url"], "title": song["title"], "channel": voice_channel})
            print(f"Adicionando música à fila: {song['title']}")

    async def search_yt(self, item):
        loop = asyncio.get_event_loop()
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = await loop.run_in_executor(None, ydl.extract_info, item, False)
                if 'entries' in info:
                    return [{'url': entry['url'], 'title': entry['title']} for entry in info['entries']]
                else:
                    return [{'url': info['url'], 'title': info['title']}]
            except Exception as e:
                print(f"Erro ao buscar no YouTube: {e}")
                return []

    async def disconnect_if_inactive(self, ctx):
        await asyncio.sleep(180)
        if not self.is_playing and not self.is_paused and self.vc and self.vc.is_connected():
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

        if "playlist" in query.lower():
            await ctx.send("Playlist sendo processada. A reprodução começará em breve.")
        else:
            await ctx.send("Música ou playlist adicionada à fila.")

        songs = await self.search_yt(query)
        if not songs:
            await ctx.send("Não foi possível encontrar a música ou a playlist.")
            return

        await self.add_songs_to_queue(ctx, songs, voice_channel)

        if not self.is_playing:
            self.is_playing = True
            self.bot.loop.create_task(self.play_music(ctx))

    @commands.command(name="skip", help="Skips the current song being played")
    async def skip(self, ctx):
        if self.vc is not None and self.vc.is_playing():
            await ctx.send(f"Pulado: {self.current_song['title']}")
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
        if self.music_queue:
            queue_message = "\n".join([song['title'] for song in self.music_queue])
            # Dividir a mensagem em partes menores se ultrapassar o limite de 2000 caracteres
            messages = textwrap.wrap(queue_message, 2000, replace_whitespace=False)
            for msg in messages:
                await ctx.send(f"Lista de reprodução atual:\n{msg}")
        else:
            await ctx.send("Não há músicas na lista de reprodução.")

    @commands.command(name="clear", aliases=["c", "bin"], help="Stops the music and clears the queue")
    async def clear(self, ctx):
        if self.vc is not None and self.vc.is_playing():
            self.vc.stop()
        self.music_queue = []
        await ctx.send("Fila limpa")

    @commands.command(name="leave", help="Makes the bot leave the voice channel")
    async def leave(self, ctx):
        if self.vc and self.vc.is_connected():
            await self.vc.disconnect()
            self.vc = None
            self.is_playing = False
            self.is_paused = False
            await ctx.send("Bot desconectado.")


def setup(bot):
    bot.add_cog(MusicCog(bot))
