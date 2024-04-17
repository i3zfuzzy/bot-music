import discord
from discord.ext import commands

from yt_dlp import YoutubeDL


class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # variaveis de controle
        self.is_playing = False
        self.is_paused = False

        # 2d array contendo [song, channel]
        self.music_queue = []
        self.YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True', 'default_search': 'auto'}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                               'options': '-vn'}

        self.vc = None

    # busca do youtube
    def search_yt(self, item):
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(item, download=False)
                if 'entries' in info:  # É uma playlist
                    videos = info['entries']
                    video = videos[0]  # Pegue apenas o primeiro vídeo da playlist
                else:  # É um vídeo único
                    video = info
                url = video['url']
                title = video['title']
            except Exception:
                return False

        return {'source': url, 'title': title}

    def play_next(self):
        if len(self.music_queue) > 0:
            self.is_playing = True

            # pega a primeira url
            m_url = self.music_queue[0][0]['source']

            # remove o primeiro elemento que esta tocando
            self.music_queue.pop(0)

            self.vc.play(discord.FFmpegOpusAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next())
        else:
            self.is_playing = False

    # checa o loop
    async def play_music(self, ctx):
        if len(self.music_queue) > 0:
            self.is_playing = True

            m_url = self.music_queue[0][0]['source']

            if self.vc is None or not self.vc.is_connected():
                self.vc = await self.music_queue[0][1].connect()
                if self.vc is None:
                    await ctx.send("Não foi possível conectar ao canal de voz")
                    return
            else:
                await self.vc.move_to(self.music_queue[0][1])

            self.music_queue.pop(0)

            self.vc.play(discord.FFmpegOpusAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next())
        else:
            self.is_playing = False

    @commands.command(name="play", aliases=["p", "playing"], help="Plays a selected song or playlist from YouTube")
    async def play(self, ctx, *args):
        query = " ".join(args)

        voice_channel = ctx.author.voice.channel
        if voice_channel is None:
            await ctx.send("Você precisa estar conectado a um canal de voz!")
        else:
            song = self.search_yt(query)
            if not song:
                await ctx.send("Não foi possível encontrar a música ou a playlist.")
            else:
                await ctx.send("Música ou playlist adicionada à fila")
                self.music_queue.append([song, voice_channel])

                if not self.is_playing:
                    await self.play_music(ctx)

    @commands.command(name="pause", help="Pauses the current song being played")
    async def pause(self, ctx, *args):
        if self.is_playing:
            self.is_playing = False
            self.is_paused = True
            self.vc.pause()
        elif self.is_paused:
            self.is_paused = False
            self.is_playing = True
            self.vc.resume()

    @commands.command(name="resume", aliases=["r"], help="Resumes playing with the discord bot")
    async def resume(self, ctx, *args):
        if self.is_paused:
            self.is_paused = False
            self.is_playing = True
            self.vc.resume()

    @commands.command(name="skip", aliases=["s"], help="Skips the current song being played")
    async def skip(self, ctx):
        if self.vc != None and self.vc:
            self.vc.stop()
            # tentar tocar a proxima musica da lista se tiver
            await self.play_music(ctx)

    @commands.command(name="next", help="Skip to the next song in the playlist")
    async def next(self, ctx):
        if self.vc is not None and self.is_playing:
            if len(self.music_queue) > 1:
                self.music_queue.pop(0)  # Remove a música atual da fila
                await self.play_music(ctx)  # Toca a próxima música
            else:
                await ctx.send("Não há mais músicas na playlist.")

    @commands.command(name="queue", aliases=["q"], help="Displays the current songs in queue")
    async def queue(self, ctx):
        retval = ""
        for i in range(0, len(self.music_queue)):
            # mostra no maximo 5 musicas na fila
            if (i > 4): break
            retval += self.music_queue[i][0]['title'] + "\n"

        if retval != "":
            await ctx.send(retval)
        else:
            await ctx.send("Não à músicas na lista")

    @commands.command(name="clear", aliases=["c", "bin"], help="Stops the music and clears the queue")
    async def clear(self, ctx):
        if self.vc != None and self.is_playing:
            self.vc.stop()
        self.music_queue = []
        await ctx.send("Fila limpa")

    @commands.command(name="leave", aliases=["disconnect", "l", "d"], help="Kick the bot from VC")
    async def dc(self, ctx):
        self.is_playing = False
        self.is_paused = False
        await self.vc.disconnect()
