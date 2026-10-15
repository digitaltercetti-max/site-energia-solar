#!/usr/bin/env python3
"""
Comercial 30 s — Oberdan System Energia Solar (16:9, estilo Apple).

Monta os clipes, aplica tipografia animada, transições (corte seco ou fade
de 0.2 s), cartela final com CTA e trilha/SFX sincronizados aos cortes.

Requisitos: Python 3.9+, ffmpeg/ffprobe no PATH, Pillow e numpy
    pip install pillow numpy

Uso básico (clipes em ./clipes, logo opcional):
    python3 montar_comercial.py
    python3 montar_comercial.py --logo logo_3d.png --trilha trilha.wav

Arquivos ausentes não travam a montagem: cena sem clipe vira uma cartela
escura com o texto, logo ausente vira uma assinatura tipográfica e, sem
--trilha, é sintetizada uma trilha-guia (120 BPM, Ré maior) com swooshes e
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

# ─────────────────────────────── Formato ────────────────────────────────
W, H = 1920, 1080          # 16:9 Full HD
FPS = 24                   # mesmo fps dos clipes gerados (evita judder)
DURACAO = 30.0
FADE = 0.2                 # duração do fade entre cenas
PUSH_IN = 0.035            # zoom lento por cena (0 desliga). 0.035 = 3,5 %
SR = 48000                 # áudio

# ────────────────────────────── Tipografia ──────────────────────────────
# SF Pro é a fonte oficial da Apple (licença só para Apple/Apps). Se estiver
# instalada no Mac, é usada; senão cai para Inter Display, a alternativa livre
# mais próxima em proporção e espaçamento.
FONTES = {
    "titulo": ["SF-Pro-Display-Semibold.otf", "SFProDisplay-Semibold.otf",
               "InterDisplay-SemiBold.otf", "Inter-SemiBold.otf"],
    "marca": ["SF-Pro-Display-Bold.otf", "SFProDisplay-Bold.otf",
              "InterDisplay-Bold.otf", "Inter-Bold.otf"],
    "texto": ["SF-Pro-Display-Medium.otf", "SFProDisplay-Medium.otf",
              "InterDisplay-Medium.otf", "Inter-Medium.otf"],
    "leve": ["SF-Pro-Display-Regular.otf", "SFProDisplay-Regular.otf",
             "InterDisplay-Regular.otf", "Inter-Regular.otf"],
}
COR_TEXTO = (245, 245, 247)        # #F5F5F7 — branco “Apple”
COR_SECUNDARIA = (161, 161, 166)   # #A1A1A6 — cinza de apoio
GRADIENTE_SOLAR = ((255, 214, 10), (255, 159, 10))   # #FFD60A → #FF9F0A
VERDE_CTA = (48, 209, 88)          # #30D158 — botão WhatsApp
TITULO_PX = 96                     # altura de corpo a 1080p
TRACKING_TITULO = -0.015           # em “em” (−1,5 %), como o SF Display
SUBIDA_PX = 28                     # deslocamento da animação de entrada

# ─────────────────────────────── Cenas ──────────────────────────────────
# clipes: lista de (padrão do nome, ponto de entrada em s). O primeiro que
# existir na pasta é usado — o nome original do roteiro vem primeiro e o
# clipe equivalente entregue vem como alternativa.
# transicao: como a cena ENTRA ("corte" seco ou "fade" de 0.2 s).
# sfx: o que toca no início da cena ("swoosh", "grave" ou ambos).
# posicao: altura do centro do texto (0 = topo, 1 = base). Padrão 0.5 (centro);
# mude nas cenas em que o assunto do clipe fica atrás do texto.
CENAS = [
    dict(inicio=0, fim=3, texto="O Poder. Redefinido.", destaque="Redefinido.",
         clipes=[("*Solar_panel_side_view*", 0.0), ("*rooftop_solar*", 0.0)],
         transicao="preto", sfx=["grave"]),
    dict(inicio=3, fim=7, texto="Tecnologia de alta eficiência.", destaque="alta eficiência.",
         clipes=[("*Sunlight_hitting_glass*", 0.5), ("*Solar_panel_grid_panning*", 2.0)],
         posicao=0.82, transicao="corte", sfx=["swoosh", "grave"]),
    dict(inicio=7, fim=10, texto="Construído para durar.",
         clipes=[("*Solar_panel_surface_texture*", 1.0), ("*Light_reflecting_on_textured_glass*", 1.0)],
         transicao="fade", sfx=["swoosh"]),
    dict(inicio=10, fim=14, texto="Pronta Entrega Imediata.", destaque="Imediata.",
         clipes=[("*Pallets_of_solar_panels*", 0.5)],
         transicao="fade", sfx=["swoosh"]),
    dict(inicio=14, fim=18, texto="Engenharia de alta precisão.",
         clipes=[("*Technician_adjusting*", 0.5), ("*Hands_tightening_metal_bracket*", 0.5)],
         posicao=0.17, transicao="corte", sfx=["swoosh", "grave"]),
    dict(inicio=18, fim=22, texto="Sua casa. Seu futuro.", destaque="Seu futuro.",
         clipes=[("*Modern_house_with_solar*", 0.5), ("*rooftop_solar*", 3.6)],
         transicao="fade", sfx=["swoosh"]),
    dict(inicio=22, fim=26, texto="Transformando o agronegócio.",
         clipes=[("*Solar_farm_aerial*", 1.0), ("*Drone_descending_over_solar_farm*", 2.0)],
         posicao=0.84, transicao="fade", sfx=["swoosh", "riser"]),
    dict(inicio=26, fim=30, final=True, transicao="corte", sfx=["impacto"]),
]

MARCA = "Oberdan System"
MARCA_SUB = "ENERGIA SOLAR"
CTA_LINHA = "21x Sem Juros  ·  +5 Anos de Mercado"
CTA_WHATSAPP = "WhatsApp  (74) 99133-5673"
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


def achar_fonte(chave: str, tamanho: int) -> ImageFont.FreeTypeFont:
    pastas = [Path(__file__).parent / "fontes", Path.home() / "Library/Fonts",
              Path("/Library/Fonts"), Path("/System/Library/Fonts"),
              Path("C:/Windows/Fonts"), Path("/usr/share/fonts"), Path.home() / ".fonts"]
    for nome in FONTES[chave]:
        for pasta in pastas:
            if not pasta.is_dir():
                continue
            direto = pasta / nome
            achados = [direto] if direto.exists() else list(pasta.rglob(nome))
            if achados:
                return ImageFont.truetype(str(achados[0]), tamanho)
    print(f"  ! fonte '{chave}' não encontrada — usando a padrão do Pillow")
    return ImageFont.load_default(tamanho)


# ═══════════════════════════ tipografia (PNG) ═══════════════════════════
def _gradiente(w: int, h: int, c1, c2) -> Image.Image:
    x = np.linspace(0, 1, max(w, 1))[None, :, None]
    cor = (np.array(c1) * (1 - x) + np.array(c2) * x).repeat(max(h, 1), axis=0)
    return Image.fromarray(cor.astype(np.uint8), "RGB")


def desenhar_linha(camada: Image.Image, texto: str, fonte, y_centro: int, *,
                   cor=COR_TEXTO, tracking=0.0, destaque: str | None = None,
                   sombra=0.45, largura_max=int(W * 0.86)) -> None:
    """Linha centralizada com tracking real (preserva kerning) e destaque em gradiente."""
    track = tracking * fonte.size
    total = fonte.getlength(texto) + track * (len(texto) - 1)
    if total > largura_max:                       # encolhe se não couber na área segura
        fonte = fonte.font_variant(size=int(fonte.size * largura_max / total))
        track = tracking * fonte.size
        total = fonte.getlength(texto) + track * (len(texto) - 1)

    altura_caixa = fonte.getbbox("H", anchor="ls")[1]   # negativo: topo da caixa-alta
    base_y = y_centro - altura_caixa / 2
    x0 = (W - total) / 2
    ini_dest = texto.rfind(destaque) if destaque else -1

    m_base = Image.new("L", (W, H), 0)
    m_dest = Image.new("L", (W, H), 0)
    d_base, d_dest = ImageDraw.Draw(m_base), ImageDraw.Draw(m_dest)
    for i, ch in enumerate(texto):
        x = x0 + fonte.getlength(texto[:i]) + track * i
        alvo = d_dest if ini_dest >= 0 and i >= ini_dest else d_base
        alvo.text((x, base_y), ch, font=fonte, fill=255, anchor="ls")

    if sombra:
        m_tudo = Image.fromarray(np.maximum(np.array(m_base), np.array(m_dest)))
        s = m_tudo.filter(ImageFilter.GaussianBlur(fonte.size * 0.22))
        s = s.point(lambda v: int(v * sombra))
        camada.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (W, H), 0)] * 3, s)), (0, 4))

    camada.paste(Image.new("RGB", (W, H), cor), (0, 0), m_base)
    if ini_dest >= 0:
        caixa = m_dest.getbbox()
        if caixa:
            grad = Image.new("RGB", (W, H))
            grad.paste(_gradiente(caixa[2] - caixa[0], caixa[3] - caixa[1], *GRADIENTE_SOLAR), caixa[:2])
            camada.paste(grad, (0, 0), m_dest)


def png_titulo(texto: str, destaque: str | None, posicao: float, destino: Path) -> Path:
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    desenhar_linha(camada, texto, achar_fonte("titulo", TITULO_PX), int(H * posicao),
                   tracking=TRACKING_TITULO, destaque=destaque, sombra=0.6)
    camada.save(destino)
    return destino


def png_degrade_inferior(destino: Path) -> Path:
    """Escurece os 40 % inferiores para o CTA ler bem sobre qualquer logo."""
    y = np.clip((np.arange(H) - H * 0.55) / (H * 0.45), 0, 1) ** 1.6
    alfa = (y * 0.78 * 255).astype(np.uint8)[:, None].repeat(W, axis=1)
    Image.merge("RGBA", (*[Image.new("L", (W, H), 0)] * 3, Image.fromarray(alfa))).save(destino)
    return destino


def png_marca(destino: Path, y_centro: int) -> Path:
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    desenhar_linha(camada, MARCA, achar_fonte("marca", 124), y_centro, tracking=-0.02, sombra=0.3)
    desenhar_linha(camada, MARCA_SUB, achar_fonte("leve", 34), y_centro + 104,
                   cor=COR_SECUNDARIA, tracking=0.32, destaque="SOLAR", sombra=0)
    camada.save(destino)
    return destino


def png_linha_cta(destino: Path, y_centro: int) -> Path:
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    desenhar_linha(camada, CTA_LINHA, achar_fonte("texto", 46), y_centro, tracking=-0.005, sombra=0.5)
    camada.save(destino)
    return destino


def png_botao_whatsapp(destino: Path, y_centro: int) -> Path:
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fonte = achar_fonte("titulo", 44)
    larg = fonte.getlength(CTA_WHATSAPP) + 2 * 46
    alt = 92
    x0, y0 = (W - larg) / 2, y_centro - alt / 2
    sombra = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sombra).rounded_rectangle((x0, y0 + 6, x0 + larg, y0 + alt + 6), alt / 2, fill=110)
    sombra = sombra.filter(ImageFilter.GaussianBlur(14))
    camada.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (W, H), 0)] * 3, sombra)))
    ImageDraw.Draw(camada).rounded_rectangle((x0, y0, x0 + larg, y0 + alt), alt / 2, fill=(*VERDE_CTA, 255))
    desenhar_linha(camada, CTA_WHATSAPP, fonte, y_centro, cor=(255, 255, 255), sombra=0)
    camada.save(destino)
    return destino


def png_fundo_cartela(destino: Path) -> Path:
    """Fundo escuro com brilho radial suave (cena sem clipe / assinatura)."""
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.6)) ** 2 + ((yy - H * 0.46) / (H * 0.6)) ** 2)
    v = np.clip(1 - r, 0, 1) ** 2
    rgb = np.stack([8 + 26 * v, 8 + 22 * v, 10 + 14 * v], axis=-1)
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


def renderizar_segmento(base: dict, camadas: list[tuple[Path, float, float | None]],
                        dur: float, destino: Path, fade_preto: float = 0.0) -> None:
    """base: {'video': Path, 'entrada': s} ou {'imagem': Path}.
    camadas: (png, início da entrada, fim da saída ou None)."""
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if "video" in base:
        cmd += ["-ss", f"{base['entrada']:.3f}", "-t", f"{dur + 0.5:.3f}", "-i", str(base["video"])]
    else:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(base["imagem"])]
    for png, _, _ in camadas:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(png)]

    grafo = [f"[0:v]{tratamento_base(dur)}" + (f",fade=t=in:st=0:d={fade_preto}" if fade_preto else "") + "[v0]"]
    atual = "v0"
    for i, (_, ini, fim) in enumerate(camadas, start=1):
        anim = f"format=rgba,fade=t=in:st={ini:.3f}:d=0.55:alpha=1"
        if fim is not None:
            anim += f",fade=t=out:st={fim - 0.3:.3f}:d=0.3:alpha=1"
        grafo.append(f"[{i}:v]{anim}[t{i}]")
        # sobe SUBIDA_PX px com ease-out cúbico durante 0.7 s
        y = f"{SUBIDA_PX}*pow(1-clip((t-{ini:.3f})/0.7,0,1),3)"
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


def sfx_brilho(dur=2.5) -> tuple[np.ndarray, float]:
    """Chime cristalino (Mi6/Si6/Mi7) para a assinatura."""
    t = np.arange(int(dur * SR)) / SR
    s = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d)
            for f, a, d in [(1318.5, 0.5, 2.2), (1975.5, 0.35, 2.8), (2637.0, 0.22, 3.5)])
    return np.stack([s * 0.9, s], 1), 0.0


def sfx_tique() -> tuple[np.ndarray, float]:
    """Tique de interface quando o botão do WhatsApp aparece."""
    t = np.arange(int(0.06 * SR)) / SR
    s = np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 90)
    return np.stack([s, s], 1), 0.0


def _midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def trilha_guia() -> np.ndarray:
    """Trilha-guia sintetizada: pad etéreo + arpejo em colcheias + pulso, 120 BPM, Ré maior.
    Serve para marcar o ritmo da edição; troque por uma trilha licenciada (--trilha)."""
    n = int(DURACAO * SR)
    t = np.arange(n) / SR
    mix = np.zeros((n, 2))
    acordes = {  # um por cena
        0: [50, 57, 62, 66, 69, 76],            # Dmaj9
        3: [50, 57, 62, 66, 69, 76],
        7: [47, 54, 62, 66, 69, 73],            # Bm9
        10: [47, 54, 62, 66, 69, 73],
        14: [43, 50, 59, 62, 66, 69],           # Gmaj9
        18: [43, 50, 59, 62, 66, 69],
        22: [45, 52, 59, 62, 64, 69],           # Asus4 (tensão)
        26: [38, 50, 57, 64, 66, 69, 74, 78],   # Dmaj9 aberto — resolução na logo
    }
    inicios = sorted(acordes)
    for k, ini in enumerate(inicios):
        fim = inicios[k + 1] if k + 1 < len(inicios) else DURACAO
        a, b = int(ini * SR), min(int((fim + 0.6) * SR), n)
        tt = t[a:b] - ini
        ataque = 1.8 if ini == 0 else 0.35
        env = np.clip(tt / ataque, 0, 1) * np.clip((fim + 0.6 - ini - tt) / 0.6, 0, 1)
        respira = 0.85 + 0.15 * np.sin(2 * np.pi * 0.25 * (tt + ini))
        for nota in acordes[ini]:
            for lado, desafino in ((0, -4), (1, 4)):
                f = _midi(nota + desafino / 100)
                voz = sum(np.sin(2 * np.pi * f * h * tt) / h ** 1.6 for h in range(1, 6))
                mix[a:b, lado] += voz * env * respira * 0.022

    batida = 0.5   # 120 BPM — todos os cortes (3, 7, 10, 14, 18, 22, 26 s) caem na batida
    for k in range(int(3 / 0.25), int(26 / 0.25)):           # arpejo em colcheias 3 s → 26 s
        ini = k * 0.25
        acorde = acordes[max(i for i in inicios if i <= ini)]
        nota = sorted(acorde)[2 + k % 4] + 12
        a = int(ini * SR)
        tt = np.arange(int(0.3 * SR)) / SR
        s = (np.sin(2 * np.pi * _midi(nota) * tt) + 0.3 * np.sin(4 * np.pi * _midi(nota) * tt)) * np.exp(-tt * 11)
        nivel = 0.05 + 0.04 * min(1, max(0, (ini - 14) / 12))    # cresce na segunda metade
        pan = 0.5 + 0.35 * (1 if k % 2 else -1)
        mix[a:a + len(s), 0] += s * nivel * (1 - pan)
        mix[a:a + len(s), 1] += s * nivel * pan
    for k in range(int(14 / batida), int(26 / batida)):      # pulso grave nas batidas 14 s → 26 s
        a = int(k * batida * SR)
        tt = np.arange(int(0.22 * SR)) / SR
        s = np.sin(2 * np.pi * (48 + 30 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 16)
        mix[a:a + len(s)] += (s * (0.10 + 0.08 * (k * batida - 14) / 12))[:, None]

    mix *= np.clip((DURACAO - t) / 1.2, 0, 1)[:, None]       # fade final
    return mix


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
        musica = trilha_guia()

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
                colocar((carregar_audio(swoosh_arq), 0.4) if swoosh_arq else sfx_swoosh(seed=k), cena["inicio"], -14)
            elif tipo == "grave":
                colocar(externo(grave_arq) if grave_arq else sfx_grave(seed=k), cena["inicio"] + 0.02, -6)
            elif tipo == "riser":
                colocar(sfx_riser(), cena["fim"], -15)
            elif tipo == "impacto":
                colocar(externo(grave_arq) if grave_arq else sfx_grave(dur=3.2, decaimento=1.3), cena["inicio"], -3)
                colocar(sfx_brilho(), cena["inicio"] + 0.05, -20)
    colocar(sfx_tique(), instante_whatsapp + 0.1, -24)

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
        fade_preto = 0.4 if cena["transicao"] == "preto" else 0.0
        rotulo = f"  {cena['inicio']:05.2f}–{cena['fim']:05.2f}s"

        if cena.get("final"):
            camadas = []
            if logo:
                base = ({"video": logo, "entrada": 0.0} if logo.suffix.lower() in (".mp4", ".mov")
                        else {"imagem": logo})
                camadas.append((png_degrade_inferior(tmp / "degrade.png"), 0.6, None))
                y_linha, y_botao = int(H * 0.80), int(H * 0.895)
                print(f"{rotulo}  logo: {logo.name}")
            else:
                base = {"imagem": fundo}
                camadas.append((png_marca(tmp / "marca.png", int(H * 0.40)), 0.25, None))
                y_linha, y_botao = int(H * 0.66), int(H * 0.77)
                print(f"{rotulo}  ! logo não encontrada — usando assinatura tipográfica")
            camadas.append((png_linha_cta(tmp / "cta.png", y_linha), 0.9, None))
            camadas.append((png_botao_whatsapp(tmp / "whatsapp.png", y_botao), 1.5, None))
            instante_whatsapp = cena["inicio"] + 1.5
            renderizar_segmento(base, camadas, dur, seg, fade_preto=0.5)
        else:
            clipe, entrada = achar_arquivo(args.clipes, cena["clipes"])
            if clipe:
                duracao_clipe = duracao_midia(clipe)
                entrada = max(0.0, min(entrada, duracao_clipe - dur - 0.05))
                base = {"video": clipe, "entrada": entrada}
                print(f"{rotulo}  {clipe.name} (a partir de {entrada:.1f}s)  “{cena['texto']}”")
            else:
                base = {"imagem": fundo}
                print(f"{rotulo}  ! clipe {cena['clipes'][0][0]} ausente — cartela escura  “{cena['texto']}”")
            titulo = png_titulo(cena["texto"], cena.get("destaque"), cena.get("posicao", 0.5), tmp / f"titulo{k + 1:02d}.png")
            entrada_txt = 0.45 if k == 0 else 0.25
            saida_txt = dur_cena - 0.1 if prox and prox["transicao"] == "corte" else dur_cena
            renderizar_segmento(base, [(titulo, entrada_txt, saida_txt)], dur, seg, fade_preto)
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
