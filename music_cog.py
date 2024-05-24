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
        self.music_queue = []
        self.current_song = None
        self.YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': True, 'default_search': 'auto', 'ignoreerrors': True}
        self.PLAYLIST_YDL_OPTIONS = {'extract_flat': True, 'default_search': 'ytsearch', 'ignoreerrors': True}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                               'options': '-vn'}

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
                # Extrair a URL completa no momento de tocar a música
                source_url = await self.extract_url(song['url'])
                source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(source_url, **self.FFMPEG_OPTIONS))
                self.vc.play(source, after=lambda e: self.bot.loop.create_task(self.song_finished(ctx, e)))
                self.is_playing = True
                await ctx.send(f"Tocando agora: {song['title']}")
                while self.vc.is_playing() or self.is_paused:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Erro ao tentar tocar a música: {e}")
                continue  # Removemos a linha que enviava a mensagem de erro

        self.is_playing = False
        await self.disconnect_if_inactive(ctx)

    async def extract_url(self, url):
        loop = asyncio.get_event_loop()
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            info = await loop.run_in_executor(None, ydl.extract_info, url)
            return info['url']

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
            self.music_queue.append({"url": song["url"], "title": song["title"], "channel": voice_channel})
            print(f"Adicionando música à fila: {song['title']}")

    async def search_yt(self, item, ctx=None):
        loop = asyncio.get_event_loop()
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch:{item}", download=False))
                if 'entries' in info:
                    entries = info['entries']
                    songs = [{'url': entry['url'], 'title': entry['title']} for entry in entries if
                             'url' in entry and 'title' in entry]
                    return songs
                elif 'url' in info and 'title' in info:
                    return [{'url': info['url'], 'title': info['title']}]
                else:
                    return []
            except Exception as e:
                print(f"Erro ao buscar no YouTube: {e}")
                return []

    async def search_playlist(self, item, ctx=None):
        loop = asyncio.get_event_loop()
        with YoutubeDL(self.PLAYLIST_YDL_OPTIONS) as ydl:
            try:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(item, download=False))
                if 'entries' in info:
                    entries = info['entries']
                    songs = [{'url': entry['url'], 'title': entry['title']} for entry in entries if
                             'url' in entry and 'title' in entry]
                    return songs
                else:
                    return []
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

        await ctx.send("Música ou playlist adicionada à fila.")

        if "playlist" in query.lower():
            songs = await self.search_playlist(query, ctx)
        else:
            songs = await self.search_yt(query, ctx)

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
            self.current_song = None  # Resetar a música atual
            self.vc.stop()
            if not self.music_queue:
                await ctx.send("Não há mais músicas na fila.")
                await self.disconnect_if_inactive(ctx)

    @commands.command(name="pause", help="Pauses the current song being played")
    async def pause(self, ctx):
        if self.vc and self.vc.is_playing():
            self.is_paused = True

    @commands.command(name="resume", help="Resumes the paused song")
    async def resume(self, ctx):
        if self.vc and self.is_paused:
            self.is_paused = False
            self.vc.resume()

    @commands.command(name="leave", help="disconnect bot")
    async def leave(self, ctx):
        if self.vc and self.vc.is_connected():
            await self.vc.disconnect()
            self.vc = None
            self.is_playing = False
            self.is_paused = False
            await ctx.send("Bot desconectado.")


def setup(bot):
    bot.add_cog(MusicCog(bot))
