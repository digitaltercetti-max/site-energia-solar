#!/usr/bin/env python3
"""
Comercial 30 s — Oberdan System Energia Solar (16:9).

Visual minimalista e premium, com tipografia de impacto (ANTON + Playfair
Display ouro) que “bate” no ritmo, e trilha hype original (trilha_hype.py).
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
# Dupla marcante: ANTON (caixa-alta condensada e pesada — o “soco”) + Playfair
# Display Black Italic em ouro metálico (o luxo). Apoio em Montserrat.
# Todas são Google Fonts sob licença OFL (uso comercial livre) e ficam em
# ./fontes. Cada entrada: (arquivos candidatos, peso do eixo wght ou None).
FONTES = {
    "impacto": (["Anton-Regular.ttf"], None),
    "ouro": (["PlayfairDisplay-Italic[wght].ttf"], 900),
    "apoio": (["Montserrat[wght].ttf"], 800),
}
FONTE_RESERVA = ["InterDisplay-Black.otf", "Inter-Black.otf", "DejaVuSans-Bold.ttf"]
COR_TEXTO = (250, 250, 250)
OURO = ((255, 244, 200), (247, 198, 74), (196, 128, 16))   # brilho → corpo → sombra
VERDE_CTA = (37, 211, 102)          # #25D366 — verde WhatsApp
TITULO_PX = 118                    # corpo do ANTON a 1080p
TRACKING_IMPACTO = 0.02            # +2 % de respiro nas maiúsculas
SLAM_ZOOM = 0.35                   # o título entra 35 % maior e “bate” no lugar
SLAM_DUR = 0.22                    # duração do slam (ease-out cúbico)

# ─────────────────────────────── Cenas ──────────────────────────────────
# titulo: (parte em ANTON branco, parte em itálico ouro).
# clipes: lista de (padrão do nome, ponto de entrada em s). O primeiro que
# existir na pasta é usado — o nome original do roteiro vem primeiro e o
# clipe equivalente entregue vem como alternativa.
# transicao: como a cena ENTRA ("corte" seco, "fade" de 0.2 s ou "preto").
# flash: clarão branco de 0.14 s no corte (acompanha os graves).
# sfx: o que toca no início da cena ("swoosh", "grave", "riser", "impacto").
# posicao: altura do centro do texto (0 = topo, 1 = base). Padrão 0.5.
CENAS = [
    dict(inicio=0, fim=3, titulo=("O PODER.", "Redefinido."),
         clipes=[("*Solar_panel_side_view*", 0.0), ("*rooftop_solar*", 0.0)],
         transicao="preto", sfx=["grave"]),
    dict(inicio=3, fim=7, titulo=("TECNOLOGIA DE", "alta eficiência."),
         clipes=[("*Sunlight_hitting_glass*", 0.5), ("*Solar_panel_grid_panning*", 2.0)],
         posicao=0.82, transicao="corte", flash=True, sfx=["swoosh", "grave"]),
    dict(inicio=7, fim=10, titulo=("CONSTRUÍDO PARA", "durar."),
         clipes=[("*Solar_panel_surface_texture*", 1.0), ("*Light_reflecting_on_textured_glass*", 1.0)],
         transicao="fade", sfx=["swoosh"]),
    dict(inicio=10, fim=14, titulo=("PRONTA ENTREGA", "imediata."),
         clipes=[("*Pallets_of_solar_panels*", 0.5)],
         transicao="fade", sfx=["swoosh"]),
    dict(inicio=14, fim=18, titulo=("ENGENHARIA DE", "alta precisão."),
         clipes=[("*Technician_adjusting*", 0.5), ("*Hands_tightening_metal_bracket*", 0.5)],
         posicao=0.17, transicao="corte", flash=True, sfx=["swoosh", "grave"]),
    dict(inicio=18, fim=22, titulo=("SUA CASA.", "Seu futuro."),
         clipes=[("*Modern_house_with_solar*", 0.5), ("*rooftop_solar*", 3.6)],
         transicao="fade", sfx=["swoosh"]),
    dict(inicio=22, fim=26, titulo=("TRANSFORMANDO O", "agronegócio."),
         clipes=[("*Solar_farm_aerial*", 1.0), ("*Drone_descending_over_solar_farm*", 2.0)],
         posicao=0.84, transicao="fade", sfx=["swoosh", "riser"]),
    dict(inicio=26, fim=30, final=True, transicao="corte", flash=True, sfx=["impacto"]),
]

MARCA = "OBERDAN SYSTEM"
MARCA_SUB = "Energia Solar"
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


_cache_fontes: dict = {}


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
            if peso and nome in nomes:
                try:
                    fonte.set_variation_by_axes([peso])
                except OSError:
                    pass
            if nome not in nomes and chave not in _cache_fontes:
                print(f"  ! fonte de '{chave}' não encontrada — usando {nome}")
            _cache_fontes[chave] = True
            return fonte
    return ImageFont.load_default(tamanho)


# ═══════════════════════════ tipografia (PNG) ═══════════════════════════
def _ouro(w: int, h: int) -> Image.Image:
    """Gradiente vertical metálico de 3 paradas."""
    y = np.linspace(0, 1, max(h, 1))[:, None, None]
    c0, c1, c2 = (np.array(c, float) for c in OURO)
    cor = np.where(y < 0.45, c0 + (c1 - c0) * (y / 0.45), c1 + (c2 - c1) * ((y - 0.45) / 0.55))
    return Image.fromarray(cor.repeat(max(w, 1), axis=1).astype(np.uint8), "RGB")


def _alfa(mascara: Image.Image) -> Image.Image:
    vazio = Image.new("L", mascara.size, 0)
    return Image.merge("RGBA", (vazio, vazio, vazio, mascara))


def desenhar_runs(camada: Image.Image, runs: list[tuple], y_centro: int, *, sombra=0.65,
                  largura_max=int(W * 0.88), espaco=0.32) -> None:
    """Desenha uma linha centralizada composta de trechos com fontes diferentes.
    runs: (texto, chave_fonte, tamanho, estilo, tracking) — estilo é "ouro" ou uma cor RGB.
    Trechos em outras fontes têm o corpo ajustado para a mesma altura de maiúscula do 1º."""
    def carregar(escala: float):
        fontes = [achar_fonte(k, max(int(t * escala), 8)) for _, k, t, _, _ in runs]
        ref = -fontes[0].getbbox("H", anchor="ls")[1]
        ajust = []
        for f, (_, k, t, _, _) in zip(fontes, runs):
            cap = -f.getbbox("H", anchor="ls")[1]
            # recarrega (font_variant perderia o peso da fonte variável)
            ajust.append(f if k == runs[0][1] else achar_fonte(k, max(int(f.size * ref / cap), 8)))
        return ajust, ref

    fontes, cap = carregar(1.0)
    larguras = lambda fs: [f.getlength(txt) + tr * f.size * (len(txt) - 1)  # noqa: E731
                           for f, (txt, *_r, tr) in zip(fs, runs)]
    total = sum(larguras(fontes)) + espaco * fontes[0].size * (len(runs) - 1)
    if total > largura_max:
        fontes, cap = carregar(largura_max / total)
        total = sum(larguras(fontes)) + espaco * fontes[0].size * (len(runs) - 1)

    base_y = y_centro + cap / 2
    x = (W - total) / 2
    m_tudo = Image.new("L", (W, H), 0)
    pintar = []
    for f, larg, (txt, _, _, estilo, tr) in zip(fontes, larguras(fontes), runs):
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        for i, ch in enumerate(txt):
            d.text((x + f.getlength(txt[:i]) + tr * f.size * i, base_y), ch, font=f, fill=255, anchor="ls")
        m_tudo = Image.fromarray(np.maximum(np.array(m_tudo), np.array(m)))
        pintar.append((m, estilo))
        x += larg + espaco * fontes[0].size

    if sombra:
        s = m_tudo.filter(ImageFilter.GaussianBlur(cap * 0.28)).point(lambda v: int(v * sombra))
        camada.alpha_composite(_alfa(s), (0, 6))
        borda = m_tudo.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.5))
        camada.alpha_composite(_alfa(borda.point(lambda v: int(v * 0.35))))
    for m, estilo in pintar:
        if estilo == "ouro":
            caixa = m.getbbox()
            if caixa:
                tinta = Image.new("RGB", (W, H))
                tinta.paste(_ouro(caixa[2] - caixa[0], caixa[3] - caixa[1]), caixa[:2])
                camada.paste(tinta, (0, 0), m)
        else:
            camada.paste(Image.new("RGB", (W, H), estilo), (0, 0), m)


def png_titulo(titulo: tuple[str, str], posicao: float, destino: Path) -> Path:
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    principal, destaque = titulo
    desenhar_runs(camada, [(principal, "impacto", TITULO_PX, COR_TEXTO, TRACKING_IMPACTO),
                           (destaque, "ouro", TITULO_PX, "ouro", 0.0)], int(H * posicao))
    camada.save(destino)
    return destino


def png_degrade_inferior(destino: Path) -> Path:
    """Escurece os 45 % inferiores para o CTA ler bem sobre qualquer logo."""
    y = np.clip((np.arange(H) - H * 0.5) / (H * 0.5), 0, 1) ** 1.4
    alfa = (y * 0.85 * 255).astype(np.uint8)[:, None].repeat(W, axis=1)
    _alfa(Image.fromarray(alfa)).save(destino)
    return destino


def png_marca(destino: Path, y_centro: int) -> Path:
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    desenhar_runs(camada, [(MARCA, "impacto", 168, COR_TEXTO, 0.035)], y_centro)
    desenhar_runs(camada, [(MARCA_SUB, "ouro", 92, "ouro", 0.0)], y_centro + 128, sombra=0.5)
    camada.save(destino)
    return destino


def png_linha_cta(destino: Path, y_centro: int) -> Path:
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    desenhar_runs(camada, [(CTA_OFERTA[0], "impacto", 80, "ouro", 0.03),
                           ("|", "apoio", 80, (150, 150, 150), 0.0),
                           (CTA_OFERTA[1], "impacto", 80, COR_TEXTO, 0.03)], y_centro, espaco=0.45)
    camada.save(destino)
    return destino


def png_botao_whatsapp(destino: Path, y_centro: int) -> Path:
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fonte = achar_fonte("apoio", 46)
    larg = fonte.getlength(CTA_WHATSAPP) + 2 * 56
    alt = 104
    x0, y0 = (W - larg) / 2, y_centro - alt / 2
    sombra = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sombra).rounded_rectangle((x0, y0 + 8, x0 + larg, y0 + alt + 8), alt / 2, fill=140)
    camada.alpha_composite(_alfa(sombra.filter(ImageFilter.GaussianBlur(16))))
    brilho = Image.new("L", (W, H), 0)   # halo verde
    ImageDraw.Draw(brilho).rounded_rectangle((x0, y0, x0 + larg, y0 + alt), alt / 2, fill=120)
    halo = Image.merge("RGBA", (*[Image.new("L", (W, H), c) for c in VERDE_CTA], brilho.filter(ImageFilter.GaussianBlur(28))))
    camada.alpha_composite(halo)
    ImageDraw.Draw(camada).rounded_rectangle((x0, y0, x0 + larg, y0 + alt), alt / 2, fill=(*VERDE_CTA, 255))
    desenhar_runs(camada, [(CTA_WHATSAPP, "apoio", 46, (255, 255, 255), 0.02)], y_centro, sombra=0)
    camada.save(destino)
    return destino


def png_fundo_cartela(destino: Path) -> Path:
    """Fundo preto com brilho radial dourado bem sutil (cena sem clipe / assinatura)."""
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.6)) ** 2 + ((yy - H * 0.46) / (H * 0.6)) ** 2)
    v = np.clip(1 - r, 0, 1) ** 2
    rgb = np.stack([8 + 34 * v, 7 + 24 * v, 6 + 8 * v], axis=-1)
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
    camadas: {'png', 'ini', 'fim' (ou None), 'modo': 'slam' | 'sobe', 'cy': centro y do texto}.
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
        if c["modo"] == "slam":
            # entra SLAM_ZOOM maior e “bate” no lugar (ease-out cúbico), ancorado no centro do texto
            z = f"1+{SLAM_ZOOM}*pow(1-clip((on/{FPS}-{ini:.3f})/{SLAM_DUR},0,1),3)"
            anim = (f"format=rgba,zoompan=z='{z}':x='{W / 2}*(1-1/zoom)':y='{c['cy']}*(1-1/zoom)'"
                    f":d=1:s={W}x{H}:fps={FPS},fade=t=in:st={ini:.3f}:d=0.1:alpha=1")
            y = "0"
        else:
            anim = f"format=rgba,fade=t=in:st={ini:.3f}:d=0.35:alpha=1"
            y = f"36*pow(1-clip((t-{ini:.3f})/0.45,0,1),3)"
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
                camadas.append(dict(png=png_degrade_inferior(tmp / "degrade.png"), ini=0.5, fim=None, modo="sobe"))
                y_linha, y_botao = int(H * 0.79), int(H * 0.90)
                print(f"{rotulo}  logo: {logo.name}")
            else:
                base = {"imagem": fundo}
                y_marca = int(H * 0.36)
                camadas.append(dict(png=png_marca(tmp / "marca.png", y_marca), ini=0.08, fim=None,
                                    modo="slam", cy=y_marca + 50))
                y_linha, y_botao = int(H * 0.66), int(H * 0.79)
                print(f"{rotulo}  ! logo não encontrada — usando assinatura tipográfica")
            # oferta “bate” em 27.0 s (stomp) e o botão sobe no clap de 27.5 s
            camadas.append(dict(png=png_linha_cta(tmp / "cta.png", y_linha), ini=0.78, fim=None,
                                modo="slam", cy=y_linha))
            camadas.append(dict(png=png_botao_whatsapp(tmp / "whatsapp.png", y_botao), ini=1.38, fim=None,
                                modo="sobe"))
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
            cy = int(H * cena.get("posicao", 0.5))
            titulo = png_titulo(cena["titulo"], cena.get("posicao", 0.5), tmp / f"titulo{k + 1:02d}.png")
            # o slam assenta no clap (meio da batida): 0.28 + 0.22 = 0.5 s após o corte
            ini_txt = 0.78 if k == 0 else 0.28
            fim_txt = dur_cena - 0.06 if prox and prox["transicao"] == "corte" else dur_cena
            renderizar_segmento(base, [dict(png=titulo, ini=ini_txt, fim=fim_txt, modo="slam", cy=cy)],
                                dur, seg, abertura)
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
