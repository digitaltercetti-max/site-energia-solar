# Comercial 30 s: Oberdan System Energia Solar

Formato 16:9 · 1920×1080 · 24 fps · H.264 + AAC 320 kbps · −14 LUFS
Estilo: visual minimalista e profissional, tipografia “type build” em Montserrat e trilha hype no clima de *O Lobo de Wall Street*.

```
comercial/
├── montar_comercial.py   # monta tudo (vídeo, tipografia, transições, áudio)
├── trilha_hype.py        # trilha original sintetizada (120 BPM, Ré menor)
├── fontes/               # Montserrat (licença OFL)
├── clipes/               # coloque aqui os clipes e a logo (não versionados)
└── saida/                # master final (não versionado)
```

## Como gerar

```bash
pip install pillow numpy scipy     # + ffmpeg (brew install ffmpeg / apt install ffmpeg)
cd comercial
python3 montar_comercial.py                                   # usa ./clipes e a trilha hype
python3 montar_comercial.py --logo clipes/logo_3d.png         # com a logo 3D
python3 montar_comercial.py --trilha trilha_licenciada.wav    # troca a trilha (SFX continuam)
```

O script procura cada clipe pelo nome do roteiro (`Solar_panel_side_view*`, `Pallets_of_solar_panels*`…) e,
se não encontrar, usa o clipe equivalente já entregue. A logo é encontrada automaticamente se o
nome do arquivo tiver “logo” (`.png`, `.jpg`, `.webp`, `.mp4` ou `.mov`).

**Ainda faltam:** o clipe dos paletes (cena 4, hoje uma cartela escura) e a imagem da logo 3D
(cena 8, hoje uma assinatura tipográfica). Basta colocá-los em `clipes/` e rodar de novo.

## 1. Timeline (EDL)

| # | Tempo | Clipe (roteiro → arquivo usado) | Texto (apoio / **palavra-chave**) | Entrada | Música / SFX |
|---|---|---|---|---|---|
| 1 | 00:00–03:00 | `Solar_panel_side_view` → *rooftop_solar* (0 s) | O PODER. / **REDEFINIDO.** | do preto 0.4 s | metal “BWAAM” + prato, coro de peito “hm-hm” com batidas no peito, prato reverso |
| 2 | 03:00–07:00 | `Sunlight_hitting_glass_surface` → *Solar_panel_grid_panning* (2 s) | TECNOLOGIA DE / **ALTA EFICIÊNCIA** | **corte + clarão branco** | DROP: entra o groove stomp-stomp-clap e o baixo, stab de metal, deep bass |
| 3 | 07:00–10:00 | `Solar_panel_surface_texture` → *Light_reflecting_on_textured_glass* (1 s) | CONSTRUÍDO PARA / **DURAR.** | fade 0.2 s | entra o chimbal; stab em Si♭ |
| 4 | 10:00–14:00 | `Pallets_of_solar_panels_stored` → *(falta: cartela)* | PRONTA / **ENTREGA** | fade 0.2 s | stab em Dó; virada de toms em 13 s |
| 5 | 14:00–18:00 | `Technician_adjusting_solar_panel` → *Hands_tightening_metal_bracket* (0.5 s) | ENGENHARIA DE / **ALTA PRECISÃO** | **corte + clarão branco** | caixa junto das palmas, bumbo sincopado, metais em síncope, deep bass |
| 6 | 18:00–22:00 | `Modern_house_with_solar_panels` → *rooftop_solar* (3.6 s) | SUA CASA. / **SEU FUTURO.** | fade 0.2 s | coro “hmm” nas cabeças de compasso |
| 7 | 22:00–26:00 | `Solar_farm_aerial_view` → *Drone_descending_over_solar_farm* (2 s) | TRANSFORMANDO O / **AGRONEGÓCIO** | fade 0.2 s | Sol menor; 24–26 s: rufo de caixa acelerando + metais em crescendo + riser |
| 8 | 26:00–30:00 | Logo 3D 16:9 → *(falta: assinatura)* | ENERGIA SOLAR / **OBERDAN SYSTEM** → 27.0 s: “21x SEM JUROS \| +5 ANOS DE MERCADO” → 27.5 s: botão WhatsApp | **corte + clarão branco** | IMPACTO: metal cheio, coro, prato e sub; groove volta em 27 s; botão final em 29 s |

Regras de edição aplicadas:
- **120 BPM.** Todos os cortes (3, 7, 10, 14, 18, 22, 26 s) caem na batida. O texto se constrói em semicolcheias e a linha sólida cai no clap, 0.5 s depois de cada corte.
- **Corte seco com clarão branco de 0.14 s** nos momentos de impacto (3 s, 14 s, 26 s), sempre com o deep bass. **Fade de 0.2 s** nas passagens de fluxo.
- **Push-in de 3.5 %** por cena, mais um grade leve: contraste +5 %, saturação +6 %, vinheta e nitidez leve após o upscale 720p→1080p.
- O áudio original dos clipes é descartado.

## 2. Tipografia: “type build” profissional

Inspirada no estilo *TYPO / TYPOGRA / TYPOGRAPHY*: uma sans geométrica pesada em caixa-alta. A palavra-chave **se constrói em três linhas alinhadas à esquerda**: duas em contorno vazado, mostrando o começo da palavra, e a última sólida e completa. Uma linha de apoio pequena e bem espaçada fica acima:

```
PRONTA            ← apoio · Montserrat SemiBold 40 px · tracking +28 % · #D7D7DC
ENT               ← eco 1 · Montserrat ExtraBold 122 px · contorno 3 px · 90 %
ENTRE             ← eco 2 · idem
ENTREGA           ← sólida · Montserrat ExtraBold 122 px · #FFFFFF
```

| Elemento | Fonte | Tamanho @1080p | Cor | Posição |
|---|---|---|---|---|
| Linha de apoio | Montserrat SemiBold, caixa-alta | 40 px, tracking +28 % | `#D7D7DC` | topo do bloco |
| Ecos (40 % e 70 % das letras) | Montserrat ExtraBold, contorno vazado | 122 px, traço de 3 px | branco a 90 % | entrelinha de 1.3× a altura da maiúscula |
| Palavra-chave | Montserrat ExtraBold | 122 px (encolhe se passar de 86 % da largura) | `#FFFFFF` | última linha |
| Marca (sem logo) | mesmo bloco: ENERGIA SOLAR / OBERDA / OBERDAN SY / **OBERDAN SYSTEM** | 122 px | branco | 36 % da altura |
| Oferta | Montserrat ExtraBold | 62 px | “21x SEM JUROS” `#FFB800`, separador cinza, resto branco | 70 % (sem logo) / 79 % (com logo) |
| Botão WhatsApp | Montserrat ExtraBold | 44 px | branco sobre pílula `#25D366` | 82 % (sem logo) / 90 % (com logo) |

- **Posição do bloco:** centralizado pela linha mais larga, com o centro vertical a 50 %. Nas cenas 2 e 7 fica embaixo (78 % e 76 %); na cena 5, em cima (24 %). O bloco sempre respeita 7 % de margem.
- **Animação:** as linhas entram uma a uma em semicolcheias (0.125 s a 120 BPM): apoio → eco 1 → eco 2 → sólida. Cada uma aparece em 0.15 s, subindo 26 px com ease-out, e a linha sólida cai no clap, 0.5 s depois do corte. A oferta entra no stomp de 27.0 s e o botão no clap de 27.5 s.
- **Legibilidade:** sombra difusa preta (blur de 14 px, 5 px abaixo), mais fraca nas linhas em contorno. Não há tarjas.
- **Licença:** Montserrat é Google Font sob **SIL OFL**, livre para uso comercial. O arquivo e a licença estão em `fontes/`.

## 3. Trilha sonora: hype estilo *O Lobo de Wall Street*

`trilha_hype.py` é uma **composição original**, sintetizada do zero: não usa nenhum trecho de música existente e pode ser veiculada sem risco de direitos autorais.

- **Andamento e tom:** 120 BPM, Ré menor. Progressão Rém → Si♭ → Dó → Rém → Si♭ → Solm → **Lá maior (tensão)** → Rém (resolução na logo).
- **Instrumentação:** coro masculino de boca fechada (“hm-hm”) com batidas no peito; groove de **pisadas em tablado + palmas em grupo** (stomp-stomp-clap); baixo serrilhado saturado com sidechain (a música “respira” a cada pisada); **naipe de metais** em stabs, síncopes e crescendo; caixa, chimbal, toms tribais, pratos e reverb de sala grande.
- **Curva de energia:**
  - 0–3 s: tensão (metal + coro de peito)
  - 3 s: DROP
  - 14 s: segunda marcha
  - 24–26 s: build com rufo e crescendo
  - 26 s: impacto e respiro
  - 27–29 s: o groove volta sob o CTA
  - 29 s: botão final
- **SFX por cima da trilha:** swoosh de ar 0.55 s antes de cada corte (−17 dB), sub drop em 0/3/14 s (−8 dB), riser até a logo (−16 dB), sub drop longo na logo (−5 dB) e tique de interface no botão do WhatsApp (−20 dB).
- **Master:** loudnorm em duas passagens para **−14 LUFS** (Instagram, YouTube, Meta Ads), true peak −1 dBTP. Para TV aberta, troque `I=-14` por `I=-23` no script (EBU R128 / ABNT NBR 15602).

**Para usar uma trilha licenciada no lugar:** busque em Artlist, Epidemic Sound ou Musicbed por “hip hop trailer stomp clap”, “luxury swagger brass”, “confident hype trailer 120 bpm” ou “wall street power hip hop”, com filtro *no vocals*. Escolha algo em 120 BPM (ou 60) para manter os cortes na batida e passe o arquivo com `--trilha`. Os SFX são mantidos.

## 4. Exportação
- Master: H.264 High, CRF 17, `yuv420p`, BT.709, 24 fps, AAC 320 kbps 48 kHz, `+faststart`.
