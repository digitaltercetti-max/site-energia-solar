# Comercial 30 s: Oberdan System Energia Solar

Formato 16:9 · 1920×1080 · 24 fps · H.264 + AAC 320 kbps · −14 LUFS
Estilo: visual minimalista e premium, com tipografia de impacto e trilha hype no clima de *O Lobo de Wall Street*.

```
comercial/
├── montar_comercial.py   # monta tudo (vídeo, tipografia, transições, áudio)
├── trilha_hype.py        # trilha original sintetizada (120 BPM, Ré menor)
├── fontes/               # Anton, Playfair Display, Montserrat (licença OFL)
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

| # | Tempo | Clipe (roteiro → arquivo usado) | Texto (ANTON + *ouro*) | Entrada | Música / SFX |
|---|---|---|---|---|---|
| 1 | 00:00–03:00 | `Solar_panel_side_view` → *rooftop_solar* (0 s) | O PODER. *Redefinido.* | do preto 0.4 s | metal “BWAAM” + prato, coro de peito “hm-hm” com batidas no peito, prato reverso |
| 2 | 03:00–07:00 | `Sunlight_hitting_glass_surface` → *Solar_panel_grid_panning* (2 s) | TECNOLOGIA DE *alta eficiência.* | **corte + clarão branco** | DROP: entra o groove stomp-stomp-clap e o baixo, stab de metal, deep bass |
| 3 | 07:00–10:00 | `Solar_panel_surface_texture` → *Light_reflecting_on_textured_glass* (1 s) | CONSTRUÍDO PARA *durar.* | fade 0.2 s | entra o chimbal; stab em Si♭ |
| 4 | 10:00–14:00 | `Pallets_of_solar_panels_stored` → *(falta: cartela)* | PRONTA ENTREGA *imediata.* | fade 0.2 s | stab em Dó; virada de toms em 13 s |
| 5 | 14:00–18:00 | `Technician_adjusting_solar_panel` → *Hands_tightening_metal_bracket* (0.5 s) | ENGENHARIA DE *alta precisão.* | **corte + clarão branco** | caixa junto das palmas, bumbo sincopado, metais em síncope, deep bass |
| 6 | 18:00–22:00 | `Modern_house_with_solar_panels` → *rooftop_solar* (3.6 s) | SUA CASA. *Seu futuro.* | fade 0.2 s | coro “hmm” nas cabeças de compasso |
| 7 | 22:00–26:00 | `Solar_farm_aerial_view` → *Drone_descending_over_solar_farm* (2 s) | TRANSFORMANDO O *agronegócio.* | fade 0.2 s | Sol menor; 24–26 s: rufo de caixa acelerando + metais em crescendo + riser |
| 8 | 26:00–30:00 | Logo 3D 16:9 → *(falta: assinatura)* | OBERDAN SYSTEM / *Energia Solar* → 27.0 s: “21x SEM JUROS \| +5 ANOS DE MERCADO” → 27.5 s: botão WhatsApp | **corte + clarão branco** | IMPACTO: metal cheio, coro, prato e sub; groove volta em 27 s; botão final em 29 s |

Regras de edição aplicadas:
- **120 BPM.** Todos os cortes (3, 7, 10, 14, 18, 22, 26 s) caem na batida. O texto “bate” no lugar exatamente no clap, 0.5 s depois de cada corte.
- **Corte seco com clarão branco de 0.14 s** nos momentos de impacto (3 s, 14 s, 26 s), sempre com o deep bass. **Fade de 0.2 s** nas passagens de fluxo.
- **Push-in de 3.5 %** por cena, mais um grade leve: contraste +5 %, saturação +6 %, vinheta e nitidez leve após o upscale 720p→1080p.
- O áudio original dos clipes é descartado.

## 2. Tipografia: “marcante”

A identidade vem do contraste entre uma **grotesca condensada pesada** em caixa-alta (o soco) e uma **serifada itálica Black em ouro metálico** (o luxo, o dinheiro), a mesma linguagem de pôster de cinema e de marcas premium.

| Elemento | Fonte | Tamanho @1080p | Tracking | Cor | Posição |
|---|---|---|---|---|---|
| Título (parte 1) | **Anton**, caixa-alta | 118 px | +2 % | `#FAFAFA` | centro; cenas 2 e 7 a 82–84 % da altura, cena 5 a 17 % |
| Título (parte 2) | **Playfair Display Black Italic** | altura de maiúscula igual à do Anton | 0 | ouro metálico vertical `#FFF4C8 → #F7C64A → #C48010` | na mesma linha de base |
| Marca (sem logo) | Anton | 168 px | +3.5 % | `#FAFAFA` | 36 % |
| “Energia Solar” | Playfair Display Black Italic | 92 px | 0 | ouro metálico | logo abaixo da marca |
| Oferta | Anton | 80 px | +3 % | “21x SEM JUROS” em ouro, separador cinza, “+5 ANOS DE MERCADO” em branco | 66 % (sem logo) / 79 % (com logo) |
| Botão WhatsApp | Montserrat ExtraBold | 46 px | +2 % | branco sobre pílula `#25D366` com halo verde | 79 % (sem logo) / 90 % (com logo) |

- **Animação “slam”:** o título entra 35 % maior e bate no lugar em 0.22 s (ease-out cúbico), com opacidade 0→100 % em 0.1 s. A oferta faz o mesmo em 27.0 s; o botão do WhatsApp sobe 36 px em 27.5 s, junto com um tique sonoro.
- **Legibilidade:** sombra difusa a 65 % (blur de 28 % da altura de maiúscula, 6 px abaixo) e um contorno escuro de 1–2 px. Não há tarjas. Na cartela com logo, a metade inferior recebe um degradê escuro até 85 %.
- **Área segura:** as linhas ocupam no máximo 88 % da largura e encolhem sozinhas se passarem disso.
- **Licença:** Anton, Playfair Display e Montserrat são Google Fonts sob **SIL OFL**, livres para uso comercial e veiculação. Os arquivos e as licenças estão em `fontes/`.

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
