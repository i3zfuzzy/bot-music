import discord
import asyncio
from discord.ext import commands
from yt_dlp import YoutubeDL
from discord.ui import View, Button


class MusicControlView(View):
    def __init__(self, music_cog, ctx):
        super().__init__(timeout=180)
        self.music_cog = music_cog
        self.ctx = ctx

    @discord.ui.button(label="⏮️ Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.music_cog.previous(interaction)

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.music_cog.skip(interaction)


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.manual_action = False
        self.music_queue = []  # Lista de músicas (dicionários com url e título)
        self.current_index = 0
        self.is_playing = False
        self.is_paused = False
        self.vc = None

        self.YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'quiet': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
            'extract_flat': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0'
        }

        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

    async def extract_stream_url(self, url):
        loop = asyncio.get_event_loop()
        ydl_opts = self.YDL_OPTIONS.copy()
        ydl_opts['extract_flat'] = False
        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                if info is None:
                    return None
                if 'url' in info:
                    return info['url']
                elif 'formats' in info:
                    for f in info['formats']:
                        if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                            return f['url']
                return None
            except Exception as e:
                print(f"Erro ao extrair URL do stream: {e}")
                return None

    def get_ctx(self, ctx_or_interaction):
        return ctx_or_interaction

    async def play_music(self, ctx):
        if not self.music_queue or self.current_index >= len(self.music_queue):
            self.is_playing = False
            await self.disconnect_if_inactive(ctx)
            return

        if self.vc is not None and self.vc.is_playing():
            self.manual_action = True
            self.vc.stop()

        self.is_playing = True
        song = self.music_queue[self.current_index]
        stream_url = await self.extract_stream_url(song["url"])

        if stream_url:
            source = discord.FFmpegPCMAudio(stream_url, **self.FFMPEG_OPTIONS)

            def after_playing(error):
                coro = self.after_song(ctx, error)
                fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    if "Already playing audio" not in str(e):
                        print(f"Erro no after_playing: {e}")

            self.vc.play(source, after=after_playing)

            message = f"🎶 Tocando agora: {song['title']}"

            if isinstance(ctx, discord.Interaction):
                await ctx.followup.send(message, view=MusicControlView(self, ctx))
            else:
                await ctx.send(message, view=MusicControlView(self, ctx))
        else:
            if isinstance(ctx, discord.Interaction):
                await ctx.followup.send("Erro ao obter a URL da música.")
            else:
                await ctx.send("Erro ao obter a URL da música.")
            await self.next_track(ctx)


    async def after_song(self, ctx, error):
        if error:
            if "Already playing audio" not in str(error):
                print(f"Erro ao tocar música: {error}")

        if self.manual_action:
            self.manual_action = False
            return  # Não executa próximo se foi manual (skip ou previous)

        await self.next_track(ctx)

    async def next_track(self, ctx):
        if self.current_index + 1 >= len(self.music_queue):
            await ctx.send("🏁 Fim da playlist.")
            await self.disconnect_if_inactive(ctx)
            self.music_queue.clear()
            self.current_index = 0
            self.is_playing = False
        else:
            self.current_index += 1
            await self.play_music(ctx)

    async def previous_track(self, ctx):
        if self.current_index == 0:
            await ctx.send("⛔ Já está na primeira música da fila.")
        else:
            self.current_index -= 1
            await self.play_music(ctx)

    @commands.command(name="play", aliases=["p", "playing"], help="Toca uma música ou playlist do YouTube")
    async def play(self, ctx, *, query: str):
        if ctx.author.voice is None:
            await ctx.send("Você precisa estar em um canal de voz para tocar música!")
            return

        if ("youtube.com/watch" in query or "youtu.be/" in query) and "list=" in query:
            await ctx.send(
                "⚠️ Parece que você forneceu o link de um **vídeo dentro de uma playlist**, "
                "e não a URL da playlist completa.\n\n"
                "Por favor, abra a playlist no YouTube e copie a URL no formato:\n"
                "`https://www.youtube.com/playlist?list=XXXXXXXXXXXX`\n"
                "Assim o bot poderá carregar a playlist corretamente. ✅"
            )
            return

        voice_channel = ctx.author.voice.channel
        if self.vc is None or not self.vc.is_connected():
            self.vc = await voice_channel.connect()
        elif self.vc.channel != voice_channel:
            await ctx.send("O bot já está conectado a outro canal de voz!")
            return

        results = await self.search_youtube(query)
        if results is None:
            await ctx.send("Não foi possível encontrar a música ou playlist.")
            return

        self.music_queue = results
        self.current_index = 0

        await ctx.send(
            f"✅ Playlist/músicas carregadas. Total: {len(results)}",)

        if not self.is_playing:
            await self.play_music(ctx)

    async def search_youtube(self, query):
        loop = asyncio.get_event_loop()
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
                songs = []

                if 'entries' in info:
                    for entry in info['entries']:
                        if entry is None:
                            continue
                        video_id = entry.get('id')
                        if video_id is None:
                            continue
                        url = f"https://www.youtube.com/watch?v={video_id}"
                        songs.append({
                            "url": url,
                            "title": entry.get("title", "Sem título")
                        })
                    return songs if songs else None

                else:
                    video_id = info.get('id')
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    return [{
                        "url": url,
                        "title": info.get("title", "Sem título")
                    }]

            except Exception as e:
                print(f"Erro ao buscar no YouTube: {e}")
                return None

    async def disconnect_if_inactive(self, ctx):
        if self.vc is not None and not self.vc.is_playing() and not self.is_paused:
            await asyncio.sleep(300)
            if self.vc is not None and not self.vc.is_playing() and not self.is_paused:
                await self.vc.disconnect()
                self.vc = None

    @commands.command(name="skip", help="Pula para a próxima música")
    async def skip(self, ctx):
        if not self.is_playing or self.vc is None:
            if isinstance(ctx, discord.Interaction):
                await ctx.followup.send("Nenhuma música está tocando no momento.", ephemeral=True)
            else:
                await ctx.send("Nenhuma música está tocando no momento.")
            return

        await self.next_track(ctx)

    @commands.command(name="previous", aliases=["prev"], help="Volta para a música anterior")
    async def previous(self, ctx):
        if not self.music_queue:
            if isinstance(ctx, discord.Interaction):
                await ctx.followup.send("Não há músicas na fila.", ephemeral=True)
            else:
                await ctx.send("Não há músicas na fila.")
            return
        await self.previous_track(ctx)

    @commands.command(name="pause", help="Pausa a música atual")
    async def pause(self, ctx):
        if self.vc is not None and self.vc.is_playing():
            self.vc.pause()
            self.is_paused = True
            await ctx.send("Música pausada.")

    @commands.command(name="resume", help="Retoma a música pausada")
    async def resume(self, ctx):
        if self.vc is not None and self.vc.is_paused():
            self.vc.resume()
            self.is_paused = False
            await ctx.send("Música retomada.")

    @commands.command(name="stop", help="Para a música e desconecta do canal de voz")
    async def stop(self, ctx):
        self.music_queue.clear()
        self.is_playing = False
        self.is_paused = False
        self.current_index = 0
        if self.vc is not None:
            if self.vc.is_playing() or self.vc.is_paused():
                self.vc.stop()
            await self.vc.disconnect(force=True)
            self.vc = None
            await ctx.send("Música parada, fila limpa e bot desconectado.")
        else:
            await ctx.send("O bot não está conectado a um canal de voz.")


async def setup(bot):
    await bot.add_cog(MusicCog(bot))
