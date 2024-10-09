import discord
import asyncio
from discord.ext import commands
from yt_dlp import YoutubeDL
import requests  # Biblioteca para baixar o arquivo PLS

class RadioSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Rádio Mágica", value="magica"),
            discord.SelectOption(label="Mundo Livre FM", value="mundo_livre"),
            discord.SelectOption(label="Rádio Mix", value="radio_mix"),
            discord.SelectOption(label="Jovem Pan", value="jovem_pan"),
            discord.SelectOption(label="Metropolitana FM", value="metropolitana"),  # Nova rádio adicionada
        ]
        super().__init__(placeholder="Escolha uma rádio...", options=options)

    async def callback(self, interaction: discord.Interaction):
        radio_choices = {
            "magica": "http://playerservices.streamtheworld.com/pls/MAG_AAC.pls",
            "mundo_livre": "https://playerservices.streamtheworld.com/api/livestream-redirect/MUNDOLIVRE_CWBAAC_64.aac?dist=site",
            "radio_mix": "https://26593.live.streamtheworld.com/MIXFM_SAOPAULOAAC.aac?dist=mix-web-player-radio-ao-vivo&354510.1708523699",
            "jovem_pan": "https://stream-166.zeno.fm/c45wbq2us3buv?zt=eyJhbGciOiJIUzI1NiJ9.eyJzdHJlYW0iOiJjNDV3YnEydXMzYnV2IiwiaG9zdCI6InN0cmVhbS0xNjYuemVuby5mbSIsInJ0dGwiOjUsImp0aSI6Im1mMGFfZUlnVFhxZWJaY0IxU2thUEEiLCJpYXQiOjE3Mjc5NjIxMjQsImV4cCI6MTcyNzk2MjE4NH0.G92OFE0J-ZbxnVqsLwuutcSeERLvLcoyGlffMXFityM",
            "metropolitana": "https://ice.fabricahost.com.br/metropolitana985sp",  # URL da nova rádio
        }

        radio_url = radio_choices[self.values[0]]

        # Verifica se é a Rádio Mágica e busca a URL de áudio do arquivo PLS
        if self.values[0] == "magica":
            radio_url = self.get_radio_url(radio_url)

        voice_channel = interaction.user.voice.channel
        if voice_channel is None:
            await interaction.response.send_message("Você precisa estar conectado a um canal de voz!")
            return

        if self.view.vc is None or not self.view.vc.is_connected():
            try:
                self.view.vc = await voice_channel.connect()
            except Exception as e:
                print(f"Erro ao conectar ao canal de voz: {e}")
                await interaction.response.send_message("Não foi possível conectar ao canal de voz.")
                return

        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(radio_url, **self.view.FFMPEG_OPTIONS))
        if self.view.vc.is_playing() or self.view.vc.is_paused():
            self.view.vc.stop()

        self.view.vc.play(source)
        await interaction.response.send_message(f"Tocando: {self.values[0]}")

    def get_radio_url(self, pls_url):
        # Faz o download do arquivo PLS
        response = requests.get(pls_url)
        if response.status_code == 200:
            # Extrai a URL do fluxo de áudio
            for line in response.text.splitlines():
                if line.startswith("File1="):
                    return line.split("=", 1)[1].strip()
        return None

    def get_radio_url(self, pls_url):
        # Faz o download do arquivo PLS
        response = requests.get(pls_url)
        if response.status_code == 200:
            # Extrai a URL do fluxo de áudio
            for line in response.text.splitlines():
                if line.startswith("File1="):
                    return line.split("=", 1)[1].strip()
        return None


class RadioView(discord.ui.View):
    def __init__(self, vc):
        super().__init__()
        self.vc = vc
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        self.add_item(RadioSelect())


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_playing = False
        self.is_paused = False
        self.music_queue = []
        self.current_song = None

        self.YDL_OPTIONS = {
            'format': 'bestaudio',
            'noplaylist': False,
            'default_search': 'ytsearch',
            'ignoreerrors': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
            'no_warnings': True,
            'http_chunk_size': 10485760  # 10MB
        }
        self.PLAYLIST_YDL_OPTIONS = {
            'extract_flat': True,
            'default_search': 'invidious',
            'ignoreerrors': True
        }
        self.MIX_YDL_OPTIONS = {
            'format': 'bestaudio',
            'extract_flat': True,
            'default_search': 'invidious',
            'ignoreerrors': True
        }
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'executable': '/usr/bin/ffmpeg',
            'options': '-vn'
        }

        self.vc = None
        self.play_lock = asyncio.Lock()

    # Função para tocar rádio ao vivo
    @commands.command(name="playradio", help="Toca uma rádio ao vivo.")
    async def playradio(self, ctx):
        voice_channel = ctx.author.voice.channel
        if voice_channel is None:
            await ctx.send("Você precisa estar conectado a um canal de voz!")
            return

        if self.vc is None or not self.vc.is_connected():
            try:
                self.vc = await voice_channel.connect()
            except Exception as e:
                print(f"Erro ao conectar ao canal de voz: {e}")
                await ctx.send("Não foi possível conectar ao canal de voz.")
                return

        view = RadioView(self.vc)
        await ctx.send("Selecione uma rádio para tocar:", view=view)

        # Inicia a verificação de inatividade em uma tarefa separada
        self.bot.loop.create_task(self.check_voice_channel_activity(ctx))

    async def check_voice_channel_activity(self, ctx):
        while True:
            await asyncio.sleep(5)  # Verifica a cada 5 segundos
            if self.vc is not None and self.vc.is_connected():
                # Verifica se o bot é o único membro no canal
                if len(self.vc.channel.members) == 1:  # Verifica se só tem o bot no canal
                    await self.vc.disconnect()
                    self.vc = None
                    await ctx.send("Desconectado do canal de voz devido à ausência de ouvintes.")
                    return

    async def play_music(self, ctx):
        async with self.play_lock:
            while self.music_queue:
                self.is_playing = True
                song = self.music_queue.pop(0)
                self.current_song = song

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
                    source_url = await self.extract_url(song['url'])
                    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(source_url, **self.FFMPEG_OPTIONS))

                    if self.vc.is_playing() or self.vc.is_paused():
                        self.vc.stop()

                    def after_playing(error):
                        if error:
                            print(f"Player error: {error}")
                        self.bot.loop.create_task(self.song_finished(ctx))

                    self.vc.play(source, after=after_playing)
                    await ctx.send(f"Tocando agora: {song['title']}")

                    # Inicia a verificação de inatividade em uma tarefa separada
                    self.bot.loop.create_task(self.check_voice_channel_activity(ctx))

                    while self.vc.is_playing() or self.is_paused:
                        await asyncio.sleep(1)
                except Exception as e:
                    print(f"Erro ao tentar tocar a música: {e}")
                    continue

            self.is_playing = False
            await self.disconnect_if_inactive(ctx)

    async def check_voice_channel_activity(self, ctx):
        while True:
            await asyncio.sleep(5)  # Verifica a cada 5 segundos
            if self.vc is not None and self.vc.is_connected():
                # Verifica se o bot é o único membro no canal
                if len(self.vc.channel.members) == 1:  # Verifica se só tem o bot no canal
                    await self.vc.disconnect()
                    self.vc = None
                    await ctx.send("Desconectado do canal de voz devido à ausência de ouvintes.")
                    return

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

    # Comandos de música (play, skip, pause, etc.)
    @commands.command(name="play", aliases=["p", "playing"], help="Plays a selected song or playlist from YouTube")
    async def play(self, ctx, *args):
        query = " ".join(args)

        voice_channel = ctx.author.voice.channel
        if voice_channel is None:
            await ctx.send("Você precisa estar conectado a um canal de voz!")
            return

        await ctx.send("Música ou playlist adicionada à fila.")
        songs = await self.search_youtube(query)
        await self.add_songs_to_queue(ctx, songs, voice_channel)

    async def search_youtube(self, query):
        loop = asyncio.get_event_loop()
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                # Instead of using invidious, just use the normal YouTube search
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))

                # Check if it's a playlist and extract entries
                if "entries" in info:
                    return [{"url": entry["url"], "title": entry.get("title", "Sem título")} for entry in
                            info["entries"] if "url" in entry]

                # Check if the response has a URL and title
                if "url" in info:
                    return [{"url": info["url"], "title": info.get("title", "Sem título")}]

                # If no URL is found, return empty
                return []
            except Exception as e:
                print(f"Error searching YouTube: {e}")
                return []

    async def disconnect_if_inactive(self, ctx):
        if self.vc is not None and not self.vc.is_playing() and not self.is_paused:
            await asyncio.sleep(300)  # Aguarda 5 minutos de inatividade
            if self.vc is not None and not self.vc.is_playing() and not self.is_paused:
                await self.vc.disconnect()
                self.vc = None

    @commands.command(name="pause", help="Pausa a música atual")
    async def pause(self, ctx):
        if self.vc is not None and self.vc.is_playing():
            self.vc.pause()
            self.is_paused = True
            await ctx.send("Música pausada.")

    @commands.command(name="resume", help="Continua a música atual")
    async def resume(self, ctx):
        if self.vc is not None and self.vc.is_paused():
            self.vc.resume()
            self.is_paused = False
            await ctx.send("Música retomada.")

    @commands.command(name="skip", help="Pula a música atual")
    async def skip(self, ctx):
        if self.vc is not None and self.vc.is_playing():
            self.vc.stop()
            await ctx.send("Música pulada.")

    @commands.command(name="stop", help="Para a música e desconecta do canal de voz")
    async def stop(self, ctx):
        if self.vc is not None:
            await self.vc.disconnect()
            self.vc = None
            await ctx.send("Parando a música e desconectando do canal de voz.")





async def setup(bot):
    await bot.add_cog(MusicCog(bot))
