# Comercial 30 s — Oberdan System Energia Solar

Formato 16:9 · 1920×1080 · 24 fps · H.264 + AAC 320 kbps · −14 LUFS
Estilo: minimalista, tecnológico, elegante, focado em conversão (linguagem Apple).

```
comercial/
├── montar_comercial.py   # monta tudo (vídeo, tipografia, transições, trilha e SFX)
├── clipes/               # coloque aqui os clipes e a logo (não versionados)
└── saida/                # master final (não versionado)
```

## Como gerar

```bash
pip install pillow numpy           # + ffmpeg instalado (brew install ffmpeg / apt install ffmpeg)
cd comercial
python3 montar_comercial.py                                   # usa ./clipes e a trilha-guia
python3 montar_comercial.py --logo clipes/logo_3d.png \
        --trilha trilha_licenciada.wav \
        --sfx-swoosh swoosh.wav --sfx-grave sub_drop.wav       # versão final
```

O script procura cada clipe pelo nome do roteiro (`Solar_panel_side_view*`, `Pallets_of_solar_panels*`…) e,
se não encontrar, usa o clipe equivalente já entregue. A logo é encontrada automaticamente se o
nome do arquivo tiver “logo” (`.png`, `.jpg`, `.webp`, `.mp4` ou `.mov`).

**Ainda faltam:** o clipe dos paletes (cena 4, hoje uma cartela escura) e a imagem da logo 3D
(cena 8, hoje uma assinatura tipográfica). Basta colocá-los em `clipes/` e rodar de novo.

## 1. Timeline (EDL)

| # | Tempo | Clipe (roteiro → arquivo usado) | Entrada | Texto em tela | Transição de entrada | Áudio no corte |
|---|---|---|---|---|---|---|
| 1 | 00:00–03:00 | `Solar_panel_side_view` → *rooftop_solar* (0 s) | 0.45 s | O Poder. **Redefinido.** | fade do preto 0.4 s | deep bass + pad abrindo |
| 2 | 03:00–07:00 | `Sunlight_hitting_glass_surface` → *Solar_panel_grid_panning* (2 s) | 0.25 s | Tecnologia de **alta eficiência.** | **corte seco** | swoosh + deep bass |
| 3 | 07:00–10:00 | `Solar_panel_surface_texture` → *Light_reflecting_on_textured_glass* (1 s) | 0.25 s | Construído para durar. | fade 0.2 s | swoosh |
| 4 | 10:00–14:00 | `Pallets_of_solar_panels_stored` → *(falta — cartela)* | 0.25 s | Pronta Entrega **Imediata.** | fade 0.2 s | swoosh |
| 5 | 14:00–18:00 | `Technician_adjusting_solar_panel` → *Hands_tightening_metal_bracket* (0.5 s) | 0.25 s | Engenharia de alta precisão. | **corte seco** | swoosh + deep bass, entra o pulso |
| 6 | 18:00–22:00 | `Modern_house_with_solar_panels` → *rooftop_solar* (3.6 s) | 0.25 s | Sua casa. **Seu futuro.** | fade 0.2 s | swoosh |
| 7 | 22:00–26:00 | `Solar_farm_aerial_view` → *Drone_descending_over_solar_farm* (2 s) | 0.25 s | Transformando o agronegócio. | fade 0.2 s | swoosh + riser (24.4→26 s) |
| 8 | 26:00–30:00 | Logo 3D 16:9 → *(falta — assinatura)* | escalonado | 26.6 s “21x Sem Juros · +5 Anos de Mercado” · 27.5 s botão “WhatsApp (74) 99133-5673” | **corte seco** + fade do preto 0.5 s | impacto grave + chime; tique no botão |

Regras de edição aplicadas:
- **Ritmo 120 BPM.** Todos os cortes (3, 7, 10, 14, 18, 22, 26 s) caem exatamente na batida, ou seja, a trilha final deve ter 120 BPM (ou 60/90 BPM com cortes no tempo forte).
- **Corte seco nos momentos de impacto** (3 s, 14 s, 26 s), sempre junto com o deep bass. **Fade de 0.2 s** nas passagens de fluxo. O fade começa no tempo nominal do corte, por isso a duração total fica em 30.00 s exatos.
- **Push-in de 3.5 %** em todas as cenas (zoom lento e contínuo, sem ease), mais um grade leve: contraste +5 %, saturação +6 %, vinheta suave e nitidez leve após o upscale 720p→1080p.
- O áudio original dos clipes é descartado.

## 2. Tipografia

| Elemento | Fonte | Tamanho @1080p | Tracking | Cor | Posição |
|---|---|---|---|---|---|
| Título das cenas | **SF Pro Display Semibold** (fallback: Inter Display SemiBold) | 96 px | −1.5 % | `#F5F5F7` | centro horizontal; vertical 50 % (cenas 2 e 7: 82–84 %, cena 5: 17 %) |
| Palavra-destaque | mesma | 96 px | −1.5 % | gradiente `#FFD60A → #FF9F0A` (sol) | — |
| Marca (sem logo) | SF Pro Display Bold | 124 px | −2 % | `#F5F5F7` | 40 % da altura |
| “ENERGIA SOLAR” | SF Pro Display Regular, caixa-alta | 34 px | +32 % | `#A1A1A6` / “SOLAR” em gradiente | abaixo da marca |
| Linha de oferta | SF Pro Display Medium | 46 px | −0.5 % | `#F5F5F7` | 80 % (com logo) / 66 % (sem logo) |
| Botão WhatsApp | SF Pro Display Semibold, branco | 44 px | 0 | pílula `#30D158`, raio 46 px, altura 92 px | 89.5 % (com logo) / 77 % (sem logo) |

- **Animação de entrada:** opacidade 0→100 % em 0.55 s, subindo 28 px com ease-out cúbico em 0.7 s. **Saída:** fade de 0.3 s antes do corte seco (nos fades, o texto sai junto com a imagem).
- **Legibilidade:** sombra difusa preta a 60 %, blur de 22 % do corpo, deslocada 4 px para baixo. Não há caixas nem tarjas. Na cartela com logo, os 40 % inferiores recebem um degradê escuro até 78 %.
- **Área segura:** os textos ficam dentro de 86 % da largura e encolhem sozinhos se não couberem.
- **SF Pro:** baixe a fonte em developer.apple.com/fonts e coloque o `.otf` em `comercial/fontes/` (ou instale-a no Mac). A licença da SF Pro restringe o uso a interfaces de produtos Apple; para veicular o comercial sem risco, mantenha a **Inter Display**, que é livre (OFL) e visualmente quase idêntica.

## 3. Áudio

### Trilha
- **Gênero:** eletrônica minimalista / cinematic tech. Pense em pads analógicos etéreos, arpejo em colcheias (pluck limpo) e sub-grave. Nada de vocal, guitarra ou bateria acústica.
- **Andamento e tom:** **120 BPM**, Ré maior (progressão Dmaj9 → Bm9 → Gmaj9 → Asus4 → Dmaj9 na logo).
- **Curva de energia:**
  - 0–3 s: pad sozinho abrindo (swell)
  - 3–14 s: entra o arpejo, ainda contido
  - 14–26 s: entra o pulso grave em semínimas e a energia cresce
  - 24.4–26 s: riser
  - 26 s: drop para silêncio e impacto, com o acorde final soando até o fade em 28.8–30 s
- **Busca em bancos licenciados** (Artlist, Epidemic Sound, Musicbed): “minimal tech corporate 120 bpm”, “apple style ambient pulse”, “cinematic innovation arpeggio”, “clean future tech”. Filtros: *no vocals*, *uplifting / inspiring*.
- A trilha incluída no script é **sintetizada como guia de ritmo**. Para veicular, troque por uma trilha licenciada com `--trilha` (ela é nivelada a −20 dBFS RMS sob os SFX).

### SFX (sincronizados no script)
| Efeito | Onde | Característica | Nível relativo |
|---|---|---|---|
| **Swoosh / whoosh de ar** | 0.55 s antes até 0.3 s depois de cada corte (3, 7, 10, 14, 18, 22 s) | ruído filtrado com corte subindo de 300 Hz para 6 kHz e panorâmica da esquerda para a direita; curto e “aéreo”, nunca metálico | −14 dB |
| **Deep bass / sub drop** | 0 s, 3 s, 14 s | seno de 78→38 Hz, decaimento de ~1 s, leve saturação e clique de ataque para soar em celular | −6 dB |
| **Riser reverso** | 24.4→26 s | swell de ruído e tom subindo uma oitava, cortado seco no impacto | −15 dB |
| **Impacto final** | 26 s (logo) | sub drop longo (3 s) + chime cristalino (Mi6/Si6/Mi7) | −3 dB / −20 dB |
| **Tique de UI** | 27.6 s (botão do WhatsApp) | clique de 2.4 kHz com 60 ms | −24 dB |

### Mixagem e master
- Loudness integrado **−14 LUFS** (Instagram, YouTube, Meta Ads), true peak **−1 dBTP**, normalização loudnorm em duas passagens.
- Mantenha os SFX por baixo da trilha nos cortes de fade e por cima nos cortes secos.
- Para TV aberta, troque `I=-14` por `I=-23` no script (padrão EBU R128 / ABNT NBR 15602).

## 4. Exportação
- Master: H.264 High, CRF 17, `yuv420p`, BT.709, 24 fps, AAC 320 kbps 48 kHz, `+faststart`.
- Para Reels/Stories (9:16), reenquadre depois; o texto já fica centralizado na maior parte das cenas.
