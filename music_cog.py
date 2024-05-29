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
        self.PLAYLIST_YDL_OPTIONS = {'extract_flat': True, 'default_search': 'auto', 'ignoreerrors': True}
        self.MIX_YDL_OPTIONS = {'format': 'bestaudio', 'extract_flat': True, 'default_search': 'auto', 'ignoreerrors': True}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                               'options': '-vn'}

        self.vc = None
        self.play_lock = asyncio.Lock()  # Lock para controlar a execução de play_music

    async def play_music(self, ctx):
        async with self.play_lock:  # Garantir que apenas uma execução de play_music aconteça por vez
            while self.music_queue:
                self.is_playing = True
                song = self.music_queue.pop(0)

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

                    # Parar qualquer áudio atual antes de tocar o novo
                    if self.vc.is_playing() or self.vc.is_paused():
                        self.vc.stop()

                    def after_playing(error):
                        if error:
                            print(f"Player error: {error}")
                        self.bot.loop.create_task(self.song_finished(ctx))

                    self.vc.play(source, after=after_playing)
                    await ctx.send(f"Tocando agora: {song['title']}")

                    while self.vc.is_playing() or self.is_paused:
                        await asyncio.sleep(1)
                except Exception as e:
                    print(f"Erro ao tentar tocar a música: {e}")
                    continue

            self.is_playing = False
            await self.disconnect_if_inactive(ctx)

    async def extract_url(self, url):
        loop = asyncio.get_event_loop()
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            info = await loop.run_in_executor(None, ydl.extract_info, url)
            return info['url']

    async def song_finished(self, ctx):
        if self.music_queue:
            await self.play_music(ctx)
        else:
            self.is_playing = False
            await self.disconnect_if_inactive(ctx)

    async def add_songs_to_queue(self, ctx, songs, voice_channel):
        if self.vc is None or not self.vc.is_connected():
            try:
                self.vc = await voice_channel.connect()
            except Exception as e:
                print(f"Erro ao conectar ao canal de voz: {e}")
                await ctx.send("Não foi possível conectar ao canal de voz.")
                return
        for song in songs:
            if song is None or "url" not in song:
                continue
            self.music_queue.append({"url": song["url"], "title": song["title"], "channel": voice_channel})
            print(f"Adicionando música à fila: {song['title']}")
        if not self.is_playing:
            self.is_playing = True
            self.bot.loop.create_task(self.play_music(ctx))

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
                    songs = []
                    for entry in entries:
                        if 'url' in entry and 'title' in entry:
                            songs.append({'url': entry['url'], 'title': entry['title']})
                    return songs
                else:
                    return []
            except Exception as e:
                print(f"Erro ao buscar no YouTube: {e}")
                return []

    async def search_mix(self, item, ctx=None):
        loop = asyncio.get_event_loop()
        with YoutubeDL(self.MIX_YDL_OPTIONS) as ydl:
            try:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(item, download=False))
                if 'entries' in info:
                    entries = info['entries']
                    songs = []
                    for entry in entries:
                        if 'url' in entry and 'title' in entry:
                            songs.append({'url': entry['url'], 'title': entry['title']})
                    return songs
                else:
                    return []
            except Exception as e:
                print(f"Erro ao buscar no YouTube: {e}")
                return []

    async def disconnect_if_inactive(self, ctx):
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
        elif "mix" in query.lower() or "start_radio" in query.lower():
            songs = await self.search_mix(query, ctx)
        else:
            songs = await self.search_yt(query, ctx)

        if not songs:
            await ctx.send("Não foi possível encontrar a música ou a playlist.")
            return

        await self.add_songs_to_queue(ctx, songs, voice_channel)

    @commands.command(name="skip", help="Skips the current song being played")
    async def skip(self, ctx):
        if self.vc is not None and self.vc.is_playing():
            self.vc.stop()
            await ctx.send("Música pulada.")
            await self.song_finished(ctx)
        else:
            await ctx.send("Não há música tocando no momento.")

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
            await ctx.send(f"Lista de reprodução atual:\n{queue_message}")
        else:
            await ctx.send("Não há músicas na lista de reprodução.")

    @commands.command(name="clear", aliases=["c", "bin"], help="Stops the music and clears the queue")
    async def clear(self, ctx):
        if self.vc is not None and self.vc.is_connected():
            self.vc.stop()
            await self.vc.disconnect()
            self.vc = None
        self.music_queue = []
        self.is_playing = False
        await ctx.send("Fila limpa.")

    @commands.command(name="leave", aliases=["disconnect", "dc"], help="Clears the queue and leaves the voice channel")
    async def leave(self, ctx):
        if self.vc is not None and self.vc.is_connected():
            if self.vc.is_playing() or self.vc.is_paused():
                self.vc.stop()
            await self.vc.disconnect()
            self.vc = None
            self.music_queue = []
            self.is_playing = False
            self.is_paused = False  # Reinicializa o estado de pausa
            self.current_song = None  # Reinicializa a música atual
            await ctx.send("Desconectado do canal de voz.")
        else:
            await ctx.send("Não estou conectado a nenhum canal de voz.")

def setup(bot):
    bot.add_cog(MusicCog(bot))

