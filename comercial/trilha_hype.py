"""
Trilha original “hype” do comercial — 30 s, 120 BPM, Ré menor.

Energia de trailer no clima de O Lobo de Wall Street: coro grave de peito
(“hm-hm”) com batidas no peito na abertura, groove stomp-stomp-clap, baixo
distorcido, naipe de metais em stabs e crescendo, rufo de caixa e impacto
final. Composição e síntese 100 % originais — nenhum trecho de música
existente é usado.

    from trilha_hype import gerar
    audio = gerar()          # ndarray (n, 2) float, 48 kHz
"""
from __future__ import annotations

import numpy as np
from scipy import signal

SR = 48000
BPM = 120
DURACAO = 30.0
_rng = np.random.default_rng(7)

# Harmonia por cena (início em s → acorde). Os cortes do vídeo caem todos na batida.
HARMONIA = [(0, "Dm"), (7, "Bb"), (10, "C"), (14, "Dm"), (18, "Bb"), (22, "Gm"), (24, "A"), (26, "Dm")]
METAIS = {  # vozes do naipe (MIDI)
    "Dm": [50, 57, 62, 65, 69], "Bb": [46, 53, 58, 62, 65], "C": [48, 55, 60, 64, 67],
    "Gm": [43, 50, 55, 58, 62], "A": [45, 52, 57, 61, 64],
}
BAIXO = {"Dm": 38, "Bb": 34, "C": 36, "Gm": 31, "A": 33}


# ───────────────────────────── utilidades ───────────────────────────────
def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def _midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def _filtro(x: np.ndarray, tipo: str, f, ordem: int = 2) -> np.ndarray:
    return signal.sosfilt(signal.butter(ordem, f, tipo, fs=SR, output="sos"), x)


def _ruido(n: int) -> np.ndarray:
    return _rng.standard_normal(n)


def _norm(x: np.ndarray) -> np.ndarray:
    return x / (np.abs(x).max() + 1e-12)


def _saw(f, t: np.ndarray) -> np.ndarray:
    """Dente de serra com polyBLEP (sem aliasing áspero). f pode variar no tempo."""
    f = np.broadcast_to(np.asarray(f, float), t.shape)
    dt = f / SR
    fase = (np.cumsum(dt) + _rng.random()) % 1.0
    s = 2 * fase - 1
    m = fase < dt
    x = fase[m] / dt[m]
    s[m] -= x + x - x * x - 1
    m = fase > 1 - dt
    x = (fase[m] - 1) / dt[m]
    s[m] -= x * x + x + x + 1
    return s


def _acorde(t: float) -> str:
    return [a for ini, a in HARMONIA if ini <= t + 1e-6][-1]


def _seno_glide(f: np.ndarray) -> np.ndarray:
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


# ───────────────────────────── bateria ──────────────────────────────────
def bumbo() -> np.ndarray:
    t = _t(0.5)
    s = _seno_glide(45 + 120 * np.exp(-t * 32)) * np.exp(-t * 7)
    s += _filtro(_ruido(len(t)), "highpass", 2500) * np.exp(-t * 250) * 0.25
    return _norm(np.tanh(2.2 * s))


def stomp() -> np.ndarray:
    """Pisada em tablado: grave encorpado + madeira."""
    t = _t(0.6)
    corpo = _seno_glide(42 + 85 * np.exp(-t * 20)) * np.exp(-t * 6)
    madeira = _norm(_filtro(_ruido(len(t)), "bandpass", [90, 700])) * np.exp(-t * 18) * 0.8
    return _norm(np.tanh(1.8 * (corpo + madeira)))


def palma() -> np.ndarray:
    """Palmas em grupo (estéreo, várias mãos)."""
    t = _t(0.5)
    canais = []
    for atrasos in ((0, 0.009, 0.019, 0.031), (0.004, 0.013, 0.024, 0.035)):
        env = sum((t >= d) * np.exp(-np.clip(t - d, 0, None) * 230) for d in atrasos)
        env = env + (t >= atrasos[-1]) * np.exp(-np.clip(t - atrasos[-1], 0, None) * 12) * 0.55
        canais.append(_filtro(_ruido(len(t)), "bandpass", [750, 5200]) * env)
    return _norm(np.stack(canais, 1))


def caixa() -> np.ndarray:
    t = _t(0.35)
    s = _norm(_filtro(_ruido(len(t)), "bandpass", [1500, 8000])) * np.exp(-t * 17)
    s += np.sin(2 * np.pi * 185 * t) * np.exp(-t * 28) * 0.7
    return _norm(s)


def chimbal(aberto: bool = False) -> np.ndarray:
    t = _t(0.3 if aberto else 0.07)
    return _norm(_filtro(_ruido(len(t)), "highpass", 7000, 4) * np.exp(-t * (14 if aberto else 85)))


def prato(dur: float = 3.0) -> np.ndarray:
    t = _t(dur)
    canais = [_norm(_filtro(_ruido(len(t)), "highpass", 3500, 4)) * np.exp(-t * 1.7)
              + _norm(_filtro(_ruido(len(t)), "bandpass", [6000, 12000])) * np.exp(-t * 3.5) * 0.5
              for _ in range(2)]
    return _norm(np.stack(canais, 1))


def tom(f0: float) -> np.ndarray:
    t = _t(0.5)
    s = _seno_glide(f0 * (1 + 0.6 * np.exp(-t * 25))) * np.exp(-t * 7)
    s += _norm(_filtro(_ruido(len(t)), "lowpass", 900)) * np.exp(-t * 30) * 0.3
    return _norm(np.tanh(1.5 * s))


def peito() -> np.ndarray:
    """Batida no peito: soco grave e abafado."""
    t = _t(0.35)
    s = _seno_glide(52 + 30 * np.exp(-t * 14)) * np.exp(-t * 12)
    s += _norm(_filtro(_ruido(len(t)), "lowpass", 320)) * np.exp(-t * 30) * 0.8
    return _norm(s)


# ───────────────────────────── harmonia ─────────────────────────────────
def baixo(nota: int, dur: float) -> np.ndarray:
    t = _t(dur)
    f = _midi(nota)
    s = _saw(f, t) * 0.7 + np.sin(2 * np.pi * f * t) * 0.6
    escuro, claro = _filtro(s, "lowpass", 320), _filtro(s, "lowpass", 1900)
    s = escuro + (claro - escuro) * np.exp(-t * 10)
    s *= np.clip(t / 0.004, 0, 1) * np.clip((dur - t) / 0.03, 0, 1)
    return _norm(np.tanh(2.5 * _norm(s)))


def metais(acorde: str | list[int], dur: float, *, crescendo: bool = False, oitava_abaixo: bool = False) -> np.ndarray:
    """Naipe de metais sintetizado: 4 vozes desafinadas por nota, “blat” de filtro no ataque."""
    notas = METAIS[acorde] if isinstance(acorde, str) else acorde
    if oitava_abaixo:
        notas = [notas[0] - 12, *notas]
    t = _t(dur)
    esq, dir_ = np.zeros(len(t)), np.zeros(len(t))
    vibrato = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.clip((t - 0.35) / 0.3, 0, 1)
    for nota in notas:
        f = _midi(nota) * (1 - 0.03 * np.exp(-t * 35)) * vibrato      # “scoop” de metal
        for i, cents in enumerate((-9, -3, 3, 9)):
            v = _saw(f * 2 ** (cents / 1200), t)
            if i < 2:
                esq += v
                dir_ += v * 0.6
            else:
                dir_ += v
                esq += v * 0.6
    if crescendo:
        brilho = (t / dur) ** 1.4
        amp = (t / dur) ** 2 * np.clip((dur - t) / 0.01, 0, 1)
    else:
        brilho = 0.45 + 0.55 * np.exp(-t * 5)
        amp = (np.clip(t / 0.012, 0, 1) * (0.7 + 0.3 * np.exp(-t * 8))
               * np.clip((dur - t) / 0.08, 0, 1))
    saida = []
    for x in (esq, dir_):
        escuro, claro = _filtro(x, "lowpass", 900), _filtro(x, "lowpass", 4500)
        saida.append((escuro + (claro - escuro) * brilho) * amp)
    return _norm(np.tanh(1.3 * _norm(np.stack(saida, 1))))


def coro(nota: int, dur: float, vozes: int = 3) -> np.ndarray:
    """Coro masculino de boca fechada (“hmm”): pulso glotal + formantes nasais."""
    t = _t(dur)
    fonte = np.zeros(len(t))
    for v in range(vozes):
        desafino = 2 ** (((v - 1) * 7) / 1200)
        vib = 1 + 0.005 * np.sin(2 * np.pi * (4.8 + v * 0.4) * t + v)
        fonte += _saw(_midi(nota) * desafino * vib, t)
    s = np.zeros(len(t))
    for fc, q, g in ((260, 4, 1.0), (1000, 6, 0.35), (2300, 8, 0.12)):
        b, a = signal.iirpeak(fc, q, fs=SR)
        s += signal.lfilter(b, a, fonte) * g
    s += _filtro(fonte, "lowpass", 400) * 0.3
    s *= np.clip(t / 0.03, 0, 1) * np.exp(-t * 2.5) * np.clip((dur - t) / 0.06, 0, 1)
    return _norm(s)


# ────────────────────────────── mixagem ─────────────────────────────────
class _Mix:
    def __init__(self) -> None:
        self.n = int((DURACAO + 3) * SR)
        self.bus = {k: np.zeros((self.n, 2)) for k in ("bateria", "grave", "musica", "coro")}
        self.envio = np.zeros((self.n, 2))
        self.pisadas: list[float] = []

    def add(self, bus: str, som: np.ndarray, em: float, db: float = 0.0, pan: float = 0.0, rev: float = 0.0) -> None:
        if som.ndim == 1:
            ang = (pan + 1) * np.pi / 4
            som = np.stack([som * np.cos(ang), som * np.sin(ang)], 1) * np.sqrt(2)
        a = int(em * SR)
        b = min(a + len(som), self.n)
        if b <= a:
            return
        trecho = som[: b - a] * 10 ** (db / 20)
        self.bus[bus][a:b] += trecho
        if rev:
            self.envio[a:b] += trecho * rev

    def pisar(self, em: float, db: float = 0.0) -> None:
        self.add("bateria", stomp(), em, db)
        self.pisadas.append(em)

    def render(self) -> np.ndarray:
        # sidechain: baixo e música “respiram” a cada pisada
        duck = np.ones(self.n)
        tt = _t(0.45)
        curva = 1 - 0.55 * np.exp(-tt / 0.11) * np.clip(tt / 0.005, 0, 1)
        for p in self.pisadas:
            a = int(p * SR)
            b = min(a + len(curva), self.n)
            duck[a:b] = np.minimum(duck[a:b], curva[: b - a])
        duck = duck[:, None]
        # reverb de sala grande (IR sintética decorrelacionada)
        ti = _t(2.2)
        ir = np.stack([_filtro(_ruido(len(ti)), "lowpass", 7000) * np.exp(-ti * 3.2) for _ in range(2)], 1)
        ir[: int(0.02 * SR)] = 0
        rev = np.stack([signal.fftconvolve(self.envio[:, c], ir[:, c])[: self.n] for c in range(2)], 1)
        rev = rev / (np.abs(rev).max() + 1e-12) * np.abs(self.envio).max() * 0.6

        # níveis dos grupos: metais à frente, grave firme sem embolar
        mix = (self.bus["bateria"] + self.bus["grave"] * duck * 0.7 + self.bus["musica"] * duck * 2.2
               + self.bus["coro"] * 1.6 + rev)
        mix = mix[: int(DURACAO * SR)]
        mix /= np.abs(mix).max() + 1e-12
        mix = np.tanh(mix * 1.6) / np.tanh(1.6)                       # cola / saturação de master
        mix *= np.clip((DURACAO - _t(DURACAO)) / 0.6, 0, 1)[:, None]   # fade final
        return mix * 0.9


# ───────────────────────────── arranjo ──────────────────────────────────
def gerar() -> np.ndarray:
    m = _Mix()

    # 00–03 s · ABERTURA: metal “BWAAM”, drone sub e o coro de peito “hm-hm”
    m.add("musica", metais("Dm", 1.8, oitava_abaixo=True), 0.0, -2, rev=0.5)
    m.add("bateria", prato(), 0.0, -9, rev=0.3)
    drone = np.sin(2 * np.pi * _midi(26) * _t(3.0)) * np.clip(_t(3.0) / 2.5, 0, 1)
    m.add("grave", drone, 0.0, -6)
    for em, nota in ((1.0, 45), (1.25, 50), (2.0, 45), (2.25, 50)):
        m.add("coro", coro(nota, 0.24), em, -3, rev=0.25)
        m.add("bateria", peito(), em, -4)
    for em in (1.75, 2.5, 2.75):
        m.add("bateria", peito(), em, -6)
    m.add("bateria", prato(1.0)[::-1] * np.linspace(0, 1, SR)[:, None] ** 2, 2.0, -10)   # prato reverso

    # 03–24 s · GROOVE stomp-stomp-clap + baixo
    for s in range(3, 24):
        m.pisar(s, -1)
        m.pisar(s + 0.25, -3)
        m.add("bateria", palma(), s + 0.5, -4, rev=0.18)
        if s >= 14:
            m.add("bateria", caixa(), s + 0.5, -9, rev=0.15)
            if s % 2:
                m.add("bateria", bumbo(), s + 0.75, -6)
        if s >= 7:
            for k in range(8):
                m.add("bateria", chimbal(aberto=(k == 6)), s + k * 0.125, -16 + (4 if k % 2 == 0 else 0),
                      pan=0.3)
        raiz = BAIXO[_acorde(s)]
        for desloc, intervalo in ((0, 0), (0.25, 0), (0.75, 10 if s % 2 == 0 else 12)):
            m.add("grave", baixo(raiz + intervalo, 0.2), s + desloc, -3)

    # stabs de metal em cada corte de cena + síncopes a partir de 14 s
    for corte in (3, 7, 10, 14, 18, 22):
        m.add("musica", metais(_acorde(corte), 0.42), corte, -3, rev=0.35)
        m.add("bateria", prato(2.0), corte, -14 if corte not in (3, 14) else -8, rev=0.2)
    for s in range(14, 22):
        if s % 2:
            m.add("musica", metais(_acorde(s), 0.18), s + 0.75, -8, rev=0.25)
        elif s not in (14, 18):
            m.add("musica", metais(_acorde(s), 0.3), s, -7, rev=0.25)
    m.add("musica", metais("Gm", 0.3), 23.0, -6, rev=0.3)
    m.add("musica", metais("Gm", 0.18), 23.75, -8, rev=0.3)
    for s in (18, 20):
        m.add("coro", coro(50, 0.5), s, -9, rev=0.4)

    # viradas de tom (tribal) antes dos cortes fortes
    for ini in (13.0, 21.0):
        for k in range(8):
            m.add("bateria", tom(170 - k * 12), ini + k * 0.125, -8 + k * 0.6, pan=0.4 - k * 0.1, rev=0.15)

    # 24–26 s · BUILD: pisadas em semínima, rufo de caixa acelerando e metal em crescendo
    for s in (24, 24.5, 25, 25.5):
        m.pisar(s, -3)
    tempos = [*np.arange(24, 25, 0.125), *np.arange(25, 25.5, 0.0625), *np.arange(25.5, 26, 0.03125)]
    for i, em in enumerate(tempos):
        m.add("bateria", caixa(), em, -20 + 16 * i / len(tempos), rev=0.1)
    m.add("musica", metais("A", 2.0, crescendo=True), 24.0, -1, rev=0.2)
    for desloc in (0, 0.25, 0.75):
        m.add("grave", baixo(BAIXO["A"], 0.2), 24 + desloc, -3)
        m.add("grave", baixo(BAIXO["A"], 0.2), 25 + desloc, -3)

    # 26 s · IMPACTO NA LOGO: metal cheio + coro + prato, groove volta em 27 s
    m.add("musica", metais("Dm", 2.4, oitava_abaixo=True), 26.0, 0, rev=0.6)
    m.add("coro", coro(50, 1.6, vozes=5), 26.0, -4, rev=0.5)
    m.add("bateria", prato(3.0), 26.0, -6, rev=0.3)
    m.pisar(26.0, 0)
    for s in (27, 28):
        m.pisar(s, -2)
        m.pisar(s + 0.25, -4)
        m.add("bateria", palma(), s + 0.5, -5, rev=0.2)
        for desloc, intervalo in ((0, 0), (0.25, 0), (0.75, 12)):
            m.add("grave", baixo(BAIXO["Dm"] + intervalo, 0.2), s + desloc, -4)
    # botão final
    m.add("musica", metais("Dm", 0.9, oitava_abaixo=True), 29.0, -1, rev=0.6)
    m.pisar(29.0, 0)
    m.add("bateria", prato(1.5), 29.0, -10, rev=0.3)

    return m.render()
