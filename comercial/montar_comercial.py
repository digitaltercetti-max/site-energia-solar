#!/usr/bin/env python3
"""
Comercial 30 s — Oberdan System Energia Solar (16:9).

Visual minimalista e profissional, tipografia “type build” em Montserrat
ExtraBold (linhas em contorno que constroem a palavra-chave no ritmo) e
trilha hype original (trilha_hype.py).
Monta os clipes, aplica as animações, transições (corte seco com clarão ou
fade de 0.2 s), cartela final com CTA e trilha/SFX sincronizados aos cortes.

Requisitos: Python 3.9+, ffmpeg/ffprobe no PATH, Pillow, numpy e scipy
    pip install pillow numpy scipy

Uso básico (clipes em ./clipes, logo opcional):
    python3 montar_comercial.py
    python3 montar_comercial.py --logo logo_3d.png --trilha trilha.wav

Arquivos ausentes não travam a montagem: cena sem clipe vira uma cartela
escura com o texto, logo ausente vira uma assinatura tipográfica e, sem
--trilha, é usada a trilha hype original (120 BPM, Ré menor) com swooshes e
graves posicionados nos cortes.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import trilha_hype

# ─────────────────────────────── Formato ────────────────────────────────
W, H = 1920, 1080          # 16:9 Full HD
FPS = 24                   # mesmo fps dos clipes gerados (evita judder)
DURACAO = 30.0
FADE = 0.2                 # duração do fade entre cenas
PUSH_IN = 0.035            # zoom lento por cena (0 desliga). 0.035 = 3,5 %
SR = 48000                 # áudio

# ────────────────────────────── Tipografia ──────────────────────────────
# Estilo “type build”: sans geométrica pesada em caixa-alta (Montserrat
# ExtraBold). A palavra-chave se constrói em 3 linhas alinhadas à esquerda —
# duas em contorno (eco parcial da palavra) e a última sólida, completa:
#       ENT
#       ENTRE
#       ENTREGA
# Uma linha de apoio menor, espaçada, fica acima do bloco. Montserrat é Google
# Font sob licença OFL (uso comercial livre) e fica em ./fontes.
FONTES = {  # (arquivos candidatos, peso do eixo wght)
    "forte": (["Montserrat[wght].ttf"], 800),
    "apoio": (["Montserrat[wght].ttf"], 600),
}
FONTE_RESERVA = ["InterDisplay-ExtraBold.otf", "Inter-ExtraBold.otf", "DejaVuSans-Bold.ttf"]
BRANCO = (255, 255, 255)
CINZA_APOIO = (215, 215, 220)
AMBAR = (255, 184, 0)               # destaque da oferta (21x sem juros)
VERDE_CTA = (37, 211, 102)          # #25D366 — verde WhatsApp
DESTAQUE_PX = 122                   # palavra-chave a 1080p
APOIO_PX = 40                       # linha de apoio
TRACKING_DESTAQUE = 0.0
TRACKING_APOIO = 0.28               # caixa-alta bem espaçada
CONTORNO_PX = 3                     # espessura do traço das linhas-eco
ECO = (0.4, 0.7)                    # fração de letras de cada linha-eco
OPACIDADE_ECO = 0.9

# ─────────────────────────────── Cenas ──────────────────────────────────
# titulo: (linha de apoio, palavra-chave que se constrói).
# clipes: lista de (padrão do nome, ponto de entrada em s). O primeiro que
# existir na pasta é usado — o nome original do roteiro vem primeiro e o
# clipe equivalente entregue vem como alternativa.
# transicao: como a cena ENTRA ("corte" seco, "fade" de 0.2 s ou "preto").
# flash: clarão branco de 0.14 s no corte (acompanha os graves).
# sfx: o que toca no início da cena ("swoosh", "grave", "riser", "impacto").
# posicao: centro vertical do bloco de texto (0 = topo, 1 = base). Padrão 0.5.
CENAS = [
    dict(inicio=0, fim=3, titulo=("O PODER.", "REDEFINIDO."),
         clipes=[("*Solar_panel_side_view*", 0.0), ("*rooftop_solar*", 0.0)],
         transicao="preto", sfx=["grave"]),
    dict(inicio=3, fim=7, titulo=("TECNOLOGIA DE", "ALTA EFICIÊNCIA"),
         clipes=[("*Sunlight_hitting_glass*", 0.5), ("*Solar_panel_grid_panning*", 2.0)],
         posicao=0.78, transicao="corte", flash=True, sfx=["swoosh", "grave"]),
    dict(inicio=7, fim=10, titulo=("CONSTRUÍDO PARA", "DURAR."),
         clipes=[("*Solar_panel_surface_texture*", 1.0), ("*Light_reflecting_on_textured_glass*", 1.0)],
         transicao="fade", sfx=["swoosh"]),
    dict(inicio=10, fim=14, titulo=("PRONTA", "ENTREGA"),
         clipes=[("*Pallets_of_solar_panels*", 0.5)],
         transicao="fade", sfx=["swoosh"]),
    dict(inicio=14, fim=18, titulo=("ENGENHARIA DE", "ALTA PRECISÃO"),
         clipes=[("*Technician_adjusting*", 0.5), ("*Hands_tightening_metal_bracket*", 0.5)],
         posicao=0.24, transicao="corte", flash=True, sfx=["swoosh", "grave"]),
    dict(inicio=18, fim=22, titulo=("SUA CASA.", "SEU FUTURO."),
         clipes=[("*Modern_house_with_solar*", 0.5), ("*rooftop_solar*", 3.6)],
         transicao="fade", sfx=["swoosh"]),
    dict(inicio=22, fim=26, titulo=("TRANSFORMANDO O", "AGRONEGÓCIO"),
         clipes=[("*Solar_farm_aerial*", 1.0), ("*Drone_descending_over_solar_farm*", 2.0)],
         posicao=0.76, transicao="fade", sfx=["swoosh", "riser"]),
    dict(inicio=26, fim=30, final=True, transicao="corte", flash=True, sfx=["impacto"]),
]

MARCA = "OBERDAN SYSTEM"
MARCA_SUB = "ENERGIA SOLAR"
CTA_OFERTA = ("21x SEM JUROS", "+5 ANOS DE MERCADO")
CTA_WHATSAPP = "WHATSAPP  (74) 99133-5673"
LOGO_PADROES = ["*logo*.png", "*logo*.jpg", "*logo*.jpeg", "*logo*.webp", "*logo*.mp4", "*logo*.mov"]


# ═════════════════════════════ utilidades ═══════════════════════════════
def rodar(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"\nffmpeg falhou:\n{' '.join(cmd)}\n\n{r.stderr[-3000:]}")


def duracao_midia(caminho: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(caminho)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def achar_arquivo(pasta: Path, padroes) -> tuple[Path, float] | tuple[None, None]:
    arquivos = sorted(p for p in pasta.iterdir() if p.is_file()) if pasta.is_dir() else []
    for padrao, entrada in padroes:
        for arq in arquivos:
            if fnmatch.fnmatch(arq.name.lower(), padrao.lower()):
                return arq, entrada
    return None, None


_avisos_fonte: set = set()


def achar_fonte(chave: str, tamanho: int) -> ImageFont.FreeTypeFont:
    nomes, peso = FONTES[chave]
    pastas = [Path(__file__).parent / "fontes", Path.home() / "Library/Fonts",
              Path("/Library/Fonts"), Path("C:/Windows/Fonts"), Path("/usr/share/fonts"),
              Path.home() / ".fonts"]
    for nome in [*nomes, *FONTE_RESERVA]:
        for pasta in pastas:
            if not pasta.is_dir():
                continue
            direto = pasta / nome
            achados = [direto] if direto.exists() else list(pasta.rglob(nome))
            if not achados:
                continue
            fonte = ImageFont.truetype(str(achados[0]), tamanho)
            if nome in nomes:
                try:
                    fonte.set_variation_by_axes([peso])
                except OSError:
                    pass
            elif chave not in _avisos_fonte:
                print(f"  ! fonte de '{chave}' não encontrada — usando {nome}")
                _avisos_fonte.add(chave)
            return fonte
    return ImageFont.load_default(tamanho)


# ═══════════════════════════ tipografia (PNG) ═══════════════════════════
def _alfa(mascara: Image.Image, cor=(0, 0, 0)) -> Image.Image:
    return Image.merge("RGBA", (*[Image.new("L", mascara.size, c) for c in cor], mascara))


def _largura(texto: str, fonte, tracking: float) -> float:
    return fonte.getlength(texto) + tracking * fonte.size * max(len(texto) - 1, 0)


def _mascara_texto(texto: str, fonte, x: float, base_y: float, tracking: float,
                   contorno: int = 0) -> Image.Image:
    """Máscara da linha com tracking real (posições via getlength preservam o kerning).
    contorno > 0 devolve só o traço (letra vazada)."""
    cheio = Image.new("L", (W, H), 0)
    traco = Image.new("L", (W, H), 0) if contorno else None
    dc = ImageDraw.Draw(cheio)
    dt = ImageDraw.Draw(traco) if contorno else None
    for i, ch in enumerate(texto):
        xi = x + fonte.getlength(texto[:i]) + tracking * fonte.size * i
        dc.text((xi, base_y), ch, font=fonte, fill=255, anchor="ls")
        if contorno:
            dt.text((xi, base_y), ch, font=fonte, fill=255, anchor="ls",
                    stroke_width=contorno, stroke_fill=255)
    if not contorno:
        return cheio
    # traço centrado no contorno da letra: letra engordada − letra erodida (um anel contínuo)
    erodido = cheio.filter(ImageFilter.MinFilter(2 * (contorno // 2) + 1)) if contorno > 1 else cheio
    anel = np.clip(np.array(traco, int) - np.array(erodido, int), 0, 255)
    return Image.fromarray(anel.astype(np.uint8))


def _pintar(camada: Image.Image, mascara: Image.Image, cor, *, sombra=0.55, opacidade=1.0) -> None:
    if sombra:
        s = mascara.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * sombra))
        camada.alpha_composite(_alfa(s), (0, 5))
    if opacidade < 1:
        mascara = mascara.point(lambda v: int(v * opacidade))
    camada.alpha_composite(_alfa(mascara, cor))


def pngs_bloco(apoio: str, destaque: str, posicao: float, prefixo: Path,
               tamanho: int = DESTAQUE_PX) -> list[Path]:
    """Gera 4 camadas (apoio, eco 1, eco 2, sólida) do bloco “type build”, prontas para
    entrar em sequência. O bloco é alinhado à esquerda e centralizado pela linha mais larga."""
    fonte = achar_fonte("forte", tamanho)
    larg_max = W * 0.86
    if _largura(destaque, fonte, TRACKING_DESTAQUE) > larg_max:
        fonte = achar_fonte("forte", int(tamanho * larg_max / _largura(destaque, fonte, TRACKING_DESTAQUE)))
    f_apoio = achar_fonte("apoio", max(int(APOIO_PX * fonte.size / DESTAQUE_PX), 24))
    cap = -fonte.getbbox("H", anchor="ls")[1]
    cap_apoio = -f_apoio.getbbox("H", anchor="ls")[1]
    passo = cap * 1.3                                   # entrelinha do empilhamento
    altura = cap_apoio + cap * 0.75 + passo * 2 + cap
    topo = min(max(H * posicao - altura / 2, H * 0.07), H * 0.93 - altura)
    x0 = (W - _largura(destaque, fonte, TRACKING_DESTAQUE)) / 2

    n = len(destaque)
    ecos = [destaque[:max(1, -(-int(n * f * 10) // 10))].rstrip() for f in ECO]   # ceil
    linhas = [
        (apoio, f_apoio, TRACKING_APOIO, topo + cap_apoio, 0, CINZA_APOIO, 1.0),
        (ecos[0], fonte, TRACKING_DESTAQUE, topo + cap_apoio + cap * 0.75 + cap, CONTORNO_PX, BRANCO, OPACIDADE_ECO),
        (ecos[1], fonte, TRACKING_DESTAQUE, topo + cap_apoio + cap * 0.75 + cap + passo, CONTORNO_PX, BRANCO, OPACIDADE_ECO),
        (destaque, fonte, TRACKING_DESTAQUE, topo + cap_apoio + cap * 0.75 + cap + passo * 2, 0, BRANCO, 1.0),
    ]
    saida = []
    for i, (txt, f, tr, base, contorno, cor, op) in enumerate(linhas):
        camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _pintar(camada, _mascara_texto(txt, f, x0, base, tr, contorno), cor,
                sombra=0.35 if contorno else 0.6, opacidade=op)
        destino = prefixo.with_name(f"{prefixo.name}_{i}.png")
        camada.save(destino)
        saida.append(destino)
    return saida


def png_linha(destino: Path, trechos: list[tuple[str, str, int, tuple, float]], y_centro: int,
              espaco: float = 0.5) -> Path:
    """Linha centralizada com trechos de cores diferentes: (texto, fonte, px, cor, tracking)."""
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fontes = [achar_fonte(k, px) for _, k, px, _, _ in trechos]
    larguras = [_largura(t, f, tr) for f, (t, _, _, _, tr) in zip(fontes, trechos)]
    gap = espaco * fontes[0].size
    x = (W - sum(larguras) - gap * (len(trechos) - 1)) / 2
    cap = -fontes[0].getbbox("H", anchor="ls")[1]
    for f, larg, (txt, _, _, cor, tr) in zip(fontes, larguras, trechos):
        _pintar(camada, _mascara_texto(txt, f, x, y_centro + cap / 2, tr), cor)
        x += larg + gap
    camada.save(destino)
    return destino


def png_degrade_inferior(destino: Path) -> Path:
    """Escurece a metade inferior para o CTA ler bem sobre qualquer logo."""
    y = np.clip((np.arange(H) - H * 0.5) / (H * 0.5), 0, 1) ** 1.4
    alfa = (y * 0.85 * 255).astype(np.uint8)[:, None].repeat(W, axis=1)
    _alfa(Image.fromarray(alfa)).save(destino)
    return destino


def png_botao_whatsapp(destino: Path, y_centro: int) -> Path:
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fonte = achar_fonte("forte", 44)
    larg = _largura(CTA_WHATSAPP, fonte, 0.04) + 2 * 56
    alt = 100
    x0, y0 = (W - larg) / 2, y_centro - alt / 2
    sombra = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sombra).rounded_rectangle((x0, y0 + 8, x0 + larg, y0 + alt + 8), alt / 2, fill=140)
    camada.alpha_composite(_alfa(sombra.filter(ImageFilter.GaussianBlur(16))))
    ImageDraw.Draw(camada).rounded_rectangle((x0, y0, x0 + larg, y0 + alt), alt / 2, fill=(*VERDE_CTA, 255))
    cap = -fonte.getbbox("H", anchor="ls")[1]
    camada.alpha_composite(_alfa(_mascara_texto(CTA_WHATSAPP, fonte, x0 + 56, y_centro + cap / 2, 0.04), BRANCO))
    camada.save(destino)
    return destino


def png_fundo_cartela(destino: Path) -> Path:
    """Fundo preto com brilho radial bem sutil (cena sem clipe / assinatura)."""
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.6)) ** 2 + ((yy - H * 0.46) / (H * 0.6)) ** 2)
    v = np.clip(1 - r, 0, 1) ** 2
    rgb = np.stack([8 + 20 * v, 8 + 20 * v, 9 + 22 * v], axis=-1)
    Image.fromarray(rgb.astype(np.uint8), "RGB").save(destino)
    return destino


# ═══════════════════════════════ vídeo ══════════════════════════════════
def tratamento_base(dur: float) -> str:
    """Upscale 720p→1080p, push-in lento e grade leve (contraste/vinheta)."""
    passos = [f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase:flags=lanczos",
              f"crop={W * 2}:{H * 2}"]
    if PUSH_IN > 0:
        n = max(int(round(dur * FPS)), 1)
        passos.append(f"zoompan=z='1+{PUSH_IN}*on/{n}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
                      f":d=1:s={W}x{H}:fps={FPS}")
    else:
        passos.append(f"scale={W}:{H}:flags=lanczos,fps={FPS}")
    passos += ["setsar=1", "eq=contrast=1.05:saturation=1.06:brightness=-0.015",
               "vignette=angle=PI/5", "unsharp=5:5:0.35",
               f"tpad=stop_mode=clone:stop_duration={dur}", f"trim=duration={dur}", "setpts=PTS-STARTPTS"]
    return ",".join(passos)


def renderizar_segmento(base: dict, camadas: list[dict], dur: float, destino: Path,
                        entrada: tuple[str, float] | None = None) -> None:
    """base: {'video': Path, 'entrada': s} ou {'imagem': Path}.
    camadas: {'png', 'ini' (s), 'fim' (s ou None)} — cada uma entra subindo e some em 0.2 s.
    entrada: ('black' | 'white', duração) — abre a cena do preto ou com clarão branco."""
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if "video" in base:
        cmd += ["-ss", f"{base['entrada']:.3f}", "-t", f"{dur + 0.5:.3f}", "-i", str(base["video"])]
    else:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(base["imagem"])]
    for c in camadas:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(c["png"])]

    abre = f",fade=t=in:st=0:d={entrada[1]}:color={entrada[0]}" if entrada else ""
    grafo = [f"[0:v]{tratamento_base(dur)}{abre}[v0]"]
    atual = "v0"
    for i, c in enumerate(camadas, start=1):
        ini = c["ini"]
        # entra rápido: opacidade em 0.15 s e sobe 26 px com ease-out cúbico em 0.35 s
        anim = f"format=rgba,fade=t=in:st={ini:.3f}:d=0.15:alpha=1"
        y = f"26*pow(1-clip((t-{ini:.3f})/0.35,0,1),3)"
        if c["fim"] is not None:
            anim += f",fade=t=out:st={c['fim'] - 0.2:.3f}:d=0.2:alpha=1"
        grafo.append(f"[{i}:v]{anim}[t{i}]")
        grafo.append(f"[{atual}][t{i}]overlay=x=0:y='{y}':eval=frame[o{i}]")
        atual = f"o{i}"
    grafo.append(f"[{atual}]format=yuv420p,fps={FPS}[saida]")

    cmd += ["-filter_complex", ";".join(grafo), "-map", "[saida]", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-t", f"{dur:.3f}", str(destino)]
    rodar(cmd)


def unir_segmentos(segmentos: list[tuple[Path, float]], transicoes: list[str], destino: Path) -> None:
    """transicoes[i] = como o segmento i+1 entra. Fade usa xfade de FADE s."""
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for arq, _ in segmentos:
        cmd += ["-i", str(arq)]
    # mesma base de tempo em tudo: concat devolve AVTB, então as entradas também usam AVTB
    grafo = [f"[{i}:v]setsar=1,fps={FPS},format=yuv420p,settb=AVTB[s{i}]" for i in range(len(segmentos))]
    atual, comprimento = "s0", segmentos[0][1]
    for i in range(1, len(segmentos)):
        saida = f"j{i}"
        if transicoes[i - 1] == "fade":
            grafo.append(f"[{atual}][s{i}]xfade=transition=fade:duration={FADE}:offset={comprimento - FADE:.3f}[{saida}]")
            comprimento += segmentos[i][1] - FADE
        else:
            grafo.append(f"[{atual}][s{i}]concat=n=2:v=1:a=0[{saida}]")
            comprimento += segmentos[i][1]
        atual = saida
    cmd += ["-filter_complex", ";".join(grafo), "-map", f"[{atual}]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", str(destino)]
    rodar(cmd)


# ═══════════════════════════════ áudio ══════════════════════════════════
def carregar_audio(caminho: Path) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(caminho), "-f", "f32le", "-ac", "2",
                        "-ar", str(SR), "-"], capture_output=True)
    if r.returncode != 0:
        sys.exit(f"não consegui ler o áudio {caminho}")
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).copy()


def _passa_baixa(x: np.ndarray, corte: np.ndarray) -> np.ndarray:
    a = 1 - np.exp(-2 * np.pi * corte / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def sfx_swoosh(pre=0.55, pos=0.3, seed=0) -> tuple[np.ndarray, float]:
    """Ar filtrado que sobe até o corte e se dissolve — panorâmica E→D."""
    rng = np.random.default_rng(seed)
    n = int((pre + pos) * SR)
    t = np.arange(n) / SR
    ruido = rng.standard_normal(n)
    sobe = np.clip(t / pre, 0, 1)
    corte = np.where(t < pre, 300 * (20 ** sobe), 6000 * np.exp(-(t - pre) * 9))
    banda = _passa_baixa(ruido, corte) - _passa_baixa(ruido, corte / 5)
    env = np.where(t < pre, sobe ** 2.5, np.exp(-(t - pre) / 0.09))
    mono = banda * env
    mono /= np.abs(mono).max() + 1e-9
    pan = np.clip(t / (pre + pos), 0, 1)
    return np.stack([mono * np.cos(pan * np.pi / 2), mono * np.sin(pan * np.pi / 2)], 1) * 1.2, pre


def sfx_grave(dur=1.6, decaimento=2.6, seed=1) -> tuple[np.ndarray, float]:
    """Deep bass / sub drop: seno 78→38 Hz com saturação e clique de ataque."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 38 + 40 * np.exp(-t * 9)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * decaimento) * np.clip(t / 0.003, 0, 1)
    s = np.tanh(1.8 * s) / np.tanh(1.8)
    s += np.random.default_rng(seed).standard_normal(n) * np.exp(-t * 350) * 0.12
    return np.stack([s, s], 1), 0.0


def sfx_riser(dur=1.6, seed=2) -> tuple[np.ndarray, float]:
    """Swell reverso que cresce até a entrada da logo."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    corte = 800 * (12 ** (t / dur))
    ruido = rng.standard_normal(n)
    r = (_passa_baixa(ruido, corte) - _passa_baixa(ruido, corte / 6)) * (t / dur) ** 3
    r /= np.abs(r).max() + 1e-9
    tom = np.sin(2 * np.pi * (220 * (2 ** (t / dur))) * t) * (t / dur) ** 4 * 0.25
    return np.stack([r * 0.6 + tom, r * 0.6 + tom], 1), dur


def sfx_tique() -> tuple[np.ndarray, float]:
    """Tique de interface quando o botão do WhatsApp aparece."""
    t = np.arange(int(0.06 * SR)) / SR
    s = np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 90)
    return np.stack([s, s], 1), 0.0


def montar_audio(destino: Path, trilha: Path | None, swoosh_arq: Path | None, grave_arq: Path | None,
                 instante_whatsapp: float) -> None:
    n = int(DURACAO * SR)
    if trilha:
        musica = carregar_audio(trilha)[:n]
        musica = np.pad(musica, ((0, n - len(musica)), (0, 0)))
        musica *= np.clip((DURACAO - np.arange(n) / SR) / 1.5, 0, 1)[:, None]
        rms = np.sqrt(np.mean(musica ** 2)) + 1e-9
        musica *= 10 ** (-20 / 20) / rms                        # trilha a ≈ −20 dBFS RMS
    else:
        musica = trilha_hype.gerar()

    sfx = np.zeros((n, 2))

    def colocar(som: tuple[np.ndarray, float], instante: float, ganho_db: float) -> None:
        audio, antecipa = som
        a = int((instante - antecipa) * SR)
        b = min(a + len(audio), n)
        if a < 0:
            audio, a = audio[-a:], 0
        sfx[a:b] += audio[: b - a] * 10 ** (ganho_db / 20)

    externo = lambda arq: (carregar_audio(arq), 0.0)  # noqa: E731
    for k, cena in enumerate(CENAS):
        for tipo in cena.get("sfx", []):
            if tipo == "swoosh":
                colocar((carregar_audio(swoosh_arq), 0.4) if swoosh_arq else sfx_swoosh(seed=k), cena["inicio"], -17)
            elif tipo == "grave":
                colocar(externo(grave_arq) if grave_arq else sfx_grave(seed=k), cena["inicio"] + 0.02, -8)
            elif tipo == "riser":
                colocar(sfx_riser(), cena["fim"], -16)
            elif tipo == "impacto":
                colocar(externo(grave_arq) if grave_arq else sfx_grave(dur=3.2, decaimento=1.3), cena["inicio"], -5)
    colocar(sfx_tique(), instante_whatsapp, -20)

    mix = musica + sfx
    mix /= max(np.abs(mix).max(), 1e-9) / 0.89                 # pico em −1 dBFS antes do loudnorm
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())


# ═══════════════════════════════ montagem ═══════════════════════════════
def main() -> None:
    aqui = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Monta o comercial 30 s da Oberdan System Energia Solar.")
    ap.add_argument("--clipes", type=Path, default=aqui / "clipes", help="pasta com os clipes e a logo")
    ap.add_argument("--logo", type=Path, help="imagem/vídeo da logo 3D 16:9 (padrão: *logo* na pasta de clipes)")
    ap.add_argument("--trilha", type=Path, help="trilha licenciada (sem ela, usa a trilha-guia sintetizada)")
    ap.add_argument("--sfx-swoosh", type=Path, help="arquivo de swoosh (pico ~0.4 s após o início)")
    ap.add_argument("--sfx-grave", type=Path, help="arquivo de deep bass / impacto")
    ap.add_argument("--saida", type=Path, default=aqui / "saida" / "oberdan_comercial_30s.mp4")
    args = ap.parse_args()

    for prog in ("ffmpeg", "ffprobe"):
        if not shutil.which(prog):
            sys.exit(f"{prog} não encontrado no PATH.")
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="oberdan_"))

    logo = args.logo
    if logo is None:
        logo, _ = achar_arquivo(args.clipes, [(p, 0.0) for p in LOGO_PADROES])
    fundo = png_fundo_cartela(tmp / "fundo.png")

    segmentos, transicoes = [], []
    instante_whatsapp = 0.0
    print("Timeline:")
    for k, cena in enumerate(CENAS):
        prox = CENAS[k + 1] if k + 1 < len(CENAS) else None
        dur_cena = cena["fim"] - cena["inicio"]
        # se a próxima cena entra com fade, este segmento se estende FADE s por baixo dela
        dur = dur_cena + (FADE if prox and prox["transicao"] == "fade" else 0.0)
        seg = tmp / f"cena{k + 1:02d}.mp4"
        abertura = ("black", 0.4) if cena["transicao"] == "preto" else ("white", 0.14) if cena.get("flash") else None
        rotulo = f"  {cena['inicio']:05.2f}–{cena['fim']:05.2f}s"

        if cena.get("final"):
            camadas = []
            if logo:
                base = ({"video": logo, "entrada": 0.0} if logo.suffix.lower() in (".mp4", ".mov")
                        else {"imagem": logo})
                camadas.append(dict(png=png_degrade_inferior(tmp / "degrade.png"), ini=0.5, fim=None))
                y_linha, y_botao = int(H * 0.79), int(H * 0.90)
                print(f"{rotulo}  logo: {logo.name}")
            else:
                base = {"imagem": fundo}
                marca = pngs_bloco(MARCA_SUB, MARCA, 0.36, tmp / "marca")
                camadas += [dict(png=png, ini=0.125 * (i + 1), fim=None) for i, png in enumerate(marca)]
                y_linha, y_botao = int(H * 0.70), int(H * 0.82)
                print(f"{rotulo}  ! logo não encontrada — usando assinatura tipográfica")
            oferta = png_linha(tmp / "cta.png", [(CTA_OFERTA[0], "forte", 62, AMBAR, 0.02),
                                                 ("|", "apoio", 62, (110, 110, 115), 0.0),
                                                 (CTA_OFERTA[1], "forte", 62, BRANCO, 0.02)], y_linha)
            # oferta entra no stomp de 27.0 s e o botão no clap de 27.5 s
            camadas.append(dict(png=oferta, ini=1.0, fim=None))
            camadas.append(dict(png=png_botao_whatsapp(tmp / "whatsapp.png", y_botao), ini=1.5, fim=None))
            instante_whatsapp = cena["inicio"] + 1.5
            renderizar_segmento(base, camadas, dur, seg, entrada=("white", 0.2))
        else:
            clipe, entrada = achar_arquivo(args.clipes, cena["clipes"])
            frase = " ".join(cena["titulo"])
            if clipe:
                duracao_clipe = duracao_midia(clipe)
                entrada = max(0.0, min(entrada, duracao_clipe - dur - 0.05))
                base = {"video": clipe, "entrada": entrada}
                print(f"{rotulo}  {clipe.name} (a partir de {entrada:.1f}s)  “{frase}”")
            else:
                base = {"imagem": fundo}
                print(f"{rotulo}  ! clipe {cena['clipes'][0][0]} ausente — cartela escura  “{frase}”")
            linhas = pngs_bloco(*cena["titulo"], cena.get("posicao", 0.5), tmp / f"titulo{k + 1:02d}")
            # as 4 linhas entram em semicolcheias (0.125 s a 120 BPM); a sólida cai no clap
            atraso = 0.5 if k == 0 else 0.0
            fim_txt = dur_cena - 0.06 if prox and prox["transicao"] == "corte" else dur_cena
            camadas = [dict(png=png, ini=atraso + 0.125 * (i + 1), fim=fim_txt) for i, png in enumerate(linhas)]
            renderizar_segmento(base, camadas, dur, seg, abertura)
        segmentos.append((seg, dur))
        if prox:
            transicoes.append(prox["transicao"])

    print("Unindo cenas…")
    video = tmp / "video.mp4"
    unir_segmentos(segmentos, transicoes, video)

    print("Montando trilha e SFX…")
    audio = tmp / "audio.wav"
    montar_audio(audio, args.trilha, args.sfx_swoosh, args.sfx_grave, instante_whatsapp)

    print("Exportando master…")
    medida = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af",
                             "loudnorm=I=-14:TP=-1.0:LRA=9:print_format=json", "-f", "null", "-"],
                            capture_output=True, text=True).stderr
    m = json.loads(medida[medida.rindex("{"):medida.rindex("}") + 1])
    loudnorm = (f"loudnorm=I=-14:TP=-1.0:LRA=9:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
                f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
                f":offset={m['target_offset']}:linear=true")
    rodar(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio),
           "-map", "0:v", "-map", "1:a", "-t", f"{DURACAO}",
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-color_primaries", "bt709",
           "-color_trc", "bt709", "-colorspace", "bt709",
           "-af", loudnorm, "-c:a", "aac", "-b:a", "320k", "-ar", str(SR),
           "-movflags", "+faststart", str(args.saida)])
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Pronto: {args.saida}  ({duracao_midia(args.saida):.2f}s)")


if __name__ == "__main__":
    main()
