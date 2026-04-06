# Prompt — Redesign Completo da UI do Claude Usage Monitor

> **Objetivo:** Redesign total da interface do Claude Usage Monitor, inspirado no TermTracker (referência visual abaixo), com a identidade visual do projeto RIAS e adição de novas features. O backend (API, polling, data store, auth, session scanner) **NÃO deve ser alterado** — apenas a camada UI (`ui/` + referências visuais em `app.py`).

## 0. PRÉ-REQUISITO OBRIGATÓRIO — UI/UX SKILL

**ANTES de escrever qualquer código, localize e leia o skill `ui-ux-pro-max`.**

Procure nesta ordem:
1. `ls ~/.claude/skills/` — procure por pasta contendo "ui-ux" ou "pro-max"
2. `find /mnt/skills -name "*.md" | grep -i "ui-ux\|pro-max"` 
3. `find . -path "*/skills/*" -name "SKILL.md" | head -20`
4. Se não encontrar, rode: `claude-code skills list` ou cheque `/mnt/skills/user/`

Quando encontrar o SKILL.md, **leia-o integralmente** e siga todas as diretrizes de design que ele define. As regras do skill têm prioridade sobre qualquer sugestão genérica de UI neste prompt — este prompt define O QUÊ construir, o skill define COMO estilizar.

---

## 1. CONTEXTO DO PROJETO

App desktop em **PySide6** que monitora o uso de tokens do Claude Code. Roda como system tray icon no Windows com popup principal.

### Estrutura de Arquivos

```
monitor-claude/
├── main.py              # Entry point, single-instance mutex (Windows)
├── app.py               # SystemTrayApp — tray icon, popup, polling, hotkey
├── api_client.py        # GET /api/oauth/usage → UsageData (NÃO ALTERAR)
├── auth.py              # Lê ~/.claude/.credentials.json (NÃO ALTERAR)
├── config.py            # AppConfig — settings.json em LOCALAPPDATA (NÃO ALTERAR)
├── cost_estimator.py    # Estimativa de custo por modelo (NÃO ALTERAR)
├── data_store.py        # SQLite: snapshots + sessions (NÃO ALTERAR)
├── models.py            # Dataclasses: UsageData, SessionData, AppSettings (NÃO ALTERAR)
├── polling_service.py   # Timer + thread para polling da API (NÃO ALTERAR)
├── process_monitor.py   # psutil para encontrar processos Claude (NÃO ALTERAR)
├── session_scanner.py   # Scan de arquivos JSONL em ~/.claude/ (NÃO ALTERAR)
├── hotkey.py            # Global hotkey Ctrl+Shift+C (NÃO ALTERAR)
├── autostart.py         # Registro no Windows startup (NÃO ALTERAR)
├── exporter.py          # Export CSV/JSON (NÃO ALTERAR)
├── logging_config.py    # Setup de logging (NÃO ALTERAR)
├── requirements.txt     # PySide6, requests, psutil
└── ui/                  # ← FOCO DO REDESIGN
    ├── __init__.py
    ├── styles.py         # Paleta de cores e QSS global
    ├── popup_window.py   # MainPopupWindow — janela principal
    ├── tab_bar.py        # TabBar customizada
    ├── data_cards.py     # Cards de métricas (tokens, sessões ativas)
    ├── session_list.py   # Lista de sessões com expand/collapse
    ├── trend_chart.py    # Gráfico de tendência (QChart)
    ├── settings_tab.py   # Aba de configurações
    └── peak_monitor.py   # NOVO — Monitor de horário de pico ET/BRT
```

### Modelos de Dados Disponíveis (para referência — NÃO alterar)

```python
@dataclass
class UsageData:
    five_hour_utilization: float          # 0-100
    five_hour_resets_at: datetime | None
    seven_day_utilization: float          # 0-100
    seven_day_resets_at: datetime | None
    seven_day_sonnet_utilization: float | None
    seven_day_opus_utilization: float | None
    extra_usage_enabled: bool
    extra_usage_utilization: float | None
    fetched_at: datetime

@dataclass
class SessionData:
    session_id: str
    slug: str
    ai_title: str | None
    project_path: str
    entrypoint: str
    git_branch: str
    started_at: datetime | None
    ended_at: datetime | None
    user_message_count: int
    token_usage: list[SessionTokenUsage]
    # Properties: total_tokens, total_cost, duration_seconds, is_active

@dataclass
class SessionTokenUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    message_count: int
    # Property: total_tokens

@dataclass
class AppSettings:
    poll_interval_seconds: int = 60
    warning_threshold: float = 70.0
    critical_threshold: float = 90.0
    notifications_enabled: bool = True
```

### Métodos do DataStore Disponíveis (usar nas novas features)

```python
data_store.get_latest_snapshot() -> UsageData | None
data_store.get_snapshots_since(since: datetime) -> list[UsageData]
data_store.get_snapshot_count() -> int
data_store.get_recent_sessions(limit=20) -> list[SessionData]
data_store.get_sessions_since(since: datetime) -> list[SessionData]
data_store.get_today_token_totals() -> dict  # {input, output, cache_creation, cache_read, total}
data_store.get_session_count_since(since: datetime) -> int
```

---

## 2. IDENTIDADE VISUAL — PALETA RIAS

**Regra absoluta:** Nenhuma cor azul, cyan, verde ou roxa pode aparecer na interface. Todo o design usa tons de carmesim, vermelho e neutros.

```python
# Cores principais
CRIMSON         = "#DC143C"    # Cor primária RIAS (accent principal)
CRIMSON_DARK    = "#B01030"    # Hover/pressed states
CRIMSON_LIGHT   = "#FF2050"    # Highlights, gráficos linha 1
CRIMSON_GLOW    = "#DC143C40"  # Glow sutil (40 = 25% opacity)

# Vermelhos secundários
EMBER           = "#FF4500"    # Accent secundário, alerts, linha 2 no gráfico
EMBER_DARK      = "#CC3700"    # Hover do accent secundário
SCARLET         = "#FF2020"    # Critical alerts
WARNING_AMBER   = "#FFB020"    # Warning states (único tom quente permitido fora do vermelho)

# Neutros (fundo escuro estilo terminal)
BG_BASE         = "#0A0A0F"    # Fundo principal (quase preto com tom frio)
BG_SURFACE      = "#12121A"    # Cards, containers elevados
BG_ELEVATED     = "#1A1A25"    # Hover states, elementos interativos
BG_OVERLAY      = "#22222E"    # Tooltips, dropdowns

# Texto
TEXT_PRIMARY     = "#F0F0F5"    # Texto principal (branco suave)
TEXT_SECONDARY   = "#A0A0B0"   # Labels, subtítulos
TEXT_MUTED       = "#606075"    # Texto terciário, timestamps
TEXT_ACCENT      = "#DC143C"    # Texto em cor accent (links, valores destaque)

# Bordas e separadores
BORDER_SUBTLE    = "#1E1E2A"   # Bordas sutis entre elementos
BORDER_DEFAULT   = "#2A2A38"   # Bordas padrão de cards
BORDER_ACCENT    = "#DC143C30" # Borda com tom accent (30 = 19% opacity)

# Status (sem verde — usar branco/cinza para "ok")
STATUS_ACTIVE    = "#F0F0F5"   # Ponto branco = ativo/ok
STATUS_WARNING   = "#FFB020"   # Amber = atenção
STATUS_CRITICAL  = "#FF2020"   # Vermelho = crítico
STATUS_INACTIVE  = "#404055"   # Cinza = inativo/offline
```

### Regras de aplicação das cores

1. **Barras de progresso (quotas):** Gradiente de CRIMSON para SCARLET conforme a utilização sobe. Fundo da barra: `BG_SURFACE`.
2. **Tab ativa:** Background `CRIMSON`, texto branco. Tabs inativas: fundo transparente, texto `TEXT_MUTED`.
3. **Cards de métricas:** Borda `BORDER_DEFAULT`, valor principal em `CRIMSON` ou `TEXT_PRIMARY` dependendo do contexto.
4. **Gráfico de tendência:** Linha 1 (5h) em `CRIMSON_LIGHT`, Linha 2 (7d) em `EMBER`. Grid: `BORDER_SUBTLE`.
5. **Sessões ativas:** Indicador `STATUS_ACTIVE` (ponto branco), não verde.
6. **Hover em itens clicáveis:** Background muda para `BG_ELEVATED`.
7. **Scrollbar:** Handle em `BORDER_DEFAULT`, track em `BG_BASE`.

---

## 3. REFERÊNCIA VISUAL — TERMTRACKER

O TermTracker é um app similar que serve de inspiração para o layout. Principais elementos a reproduzir (adaptados):

### Layout do TermTracker (4 telas de referência):

**Tela 1 — Usage Dashboard:**
- Topo: nome do app + indicador "live" + badge do plano
- Seção de Quotas: barras de progresso para Session (5h) e Weekly (7d), com countdown de reset e porcentagem
- Bloco "Claude Code": total de tokens, sessões, mensagens, custo estimado desde data X
- Breakdown: cache read, cache write, input, output em texto colorido
- "Today's Usage": tokens totais do dia com estimativa de custo
- Breakdown do dia: cache read, cache write, input, output
- "Last Hour": taxa de tokens/min
- Gráfico sparkline de 14 dias com seletor de range

**Tela 2 — Process Monitor:**
- Lista de processos agrupados por terminal (Warp, Terminal)
- Cada processo: nome do projeto, branch (HEAD), tamanho em MB, uptime
- Botão X para terminar processo
- "End All" em vermelho

**Tela 3 — Usage (detalhada):**
- Gráfico de tendência 14 dias (msgs vs tokens como linhas separadas)
- Stats: msgs/day, total msgs, total tokens
- Seção "Models": barra horizontal mostrando proporção de uso por modelo
- Lista de modelos: opus-4-6, opus-4-5, sonnet-4-6, etc. com tokens in/out
- Seção "Sessions": lista com nome, status (active), contagem, uptime

**Tela 4 — Usage + Codex/Cursor:**
- Sessions com indicador "active" e horários
- "Peak Hours": heatmap visual mostrando horários de pico
- Seções para ferramentas externas (Codex, Cursor) com stats próprias

---

## 4. ESPECIFICAÇÃO DO REDESIGN

### 4.1 Janela Principal

- **Largura:** expandir de 420px para **560px**
- **Altura:** dinâmica (mínimo 500px, máximo ~85% da tela), com scroll interno
- Manter: frameless, stays-on-top, translucent background, rounded corners, shadow
- Manter: click-outside-to-close, position-near-tray
- **Novo:** animação de fade-in ao abrir (opacity 0→1 em ~150ms)

### 4.2 Header

- Lado esquerdo: ícone/logo "RIAS Monitor" em `CRIMSON` + texto do nome
- Lado direito: badge com o plano (ex: "Max 5x", "Pro") — extrair do contexto se disponível, senão mostrar "Pro"
- Indicador "live" pulsante (bolinha que faz pulse animation) quando polling está ativo
- Botão fechar (✕) no canto direito

### 4.3 Tab Bar

- Tabs: **Dashboard** | **Sessions** | **Processes** | **Config**
- Estilo: tab ativa com underline `CRIMSON` de 2px (ao invés de fundo preenchido), texto `TEXT_PRIMARY`
- Tabs inativas: texto `TEXT_MUTED`, sem underline
- Animação: underline desliza suavemente entre tabs

### 4.4 Tab: Dashboard (antiga "Usage" — REDESIGN COMPLETO)

#### Seção: Quotas
- **5-Hour Session**: barra de progresso horizontal com gradiente
  - Porcentagem grande ao lado direito da label
  - Countdown de reset abaixo: "resets in Xh Ym"
  - Cor da barra: gradiente `CRIMSON` → `SCARLET` conforme sobe
- **7-Day Usage**: mesma estrutura, cor diferente (`EMBER`)
- Se disponível, mostrar barras separadas para Sonnet e Opus (collapsible)
- Se extra_usage habilitado, mostrar barra de "Extra Usage" em `WARNING_AMBER`

#### Seção: Today's Usage (NOVA)
- Card destacado com borda `BORDER_ACCENT`
- Valor principal: total de tokens hoje em tamanho grande (ex: "63.2M tokens")
- Subtítulo: estimativa de custo "~$62.78 API list est."
- Grid 2x2 abaixo com mini-stats:
  - Cache Read | Cache Write | Input | Output
  - Usar `data_store.get_today_token_totals()` para os dados
- "Last Hour" com tokens/min calculado dos snapshots da última hora

#### Seção: Trend Chart
- Manter o QChart existente mas melhorar o visual:
  - Fundo transparente
  - Grid lines em `BORDER_SUBTLE` (quase invisíveis)
  - Linha 5h: `CRIMSON_LIGHT`, Linha 7d: `EMBER`
  - Seletores de range: 24h, 7d, 30d — estilo pill buttons
  - Legenda compacta abaixo do gráfico
- Altura: 160px

#### Seção: Peak Hours Monitor (NOVA — CRÍTICA)

Monitor de horário de pico que mostra em tempo real se o usuário está dentro ou fora do período de pico da Anthropic. Componente novo: `ui/peak_monitor.py`.

**Lógica de pico (hardcoded):**
- **Peak period:** 8:00 AM – 2:00 PM Eastern Time (ET), weekdays (Mon-Fri)
- **Off-peak:** fora desse horário + fins de semana inteiros
- Fuso ET = `America/New_York` (considerar horário de verão automaticamente)
- Fuso BRT = `America/Sao_Paulo` (considerar horário de verão automaticamente)
- Usar `zoneinfo.ZoneInfo` do Python 3.9+ (já disponível, sem dependência extra)

**Layout do componente:**

```
┌──────────────────────────────────────────────────────┐
│  ⚡ PEAK STATUS                                      │
│                                                      │
│           ON-PEAK  /  OFF-PEAK                       │
│     (texto grande, cor dinâmica)                     │
│                                                      │
│        Off-peak starts in:                           │
│           02:14:37                                   │
│     (countdown grande estilo relógio, atualiza 1/s)  │
│                                                      │
│  EASTERN TIME (ET)                                   │
│  ├──────████████████░░░░░░░░░░░░░░░──────┤           │
│  12a   4a   8a  [==PEAK==]  2p   6p   10p  12a      │
│                  ▲ cursor "now"                       │
│                                                      │
│  BRASÍLIA (BRT)                                      │
│  ├────────────████████████░░░░░░░░░░░────┤           │
│  12a   4a   9a  [==PEAK==]  3p   7p   11p  12a      │
│                  ▲ cursor "now"                       │
│                                                      │
│  ┌─────────────┬─────────────┬─────────────┐         │
│  │ LOCAL ZONE  │ LOCAL TIME  │ EASTERN TIME │         │
│  │ Sao_Paulo   │ 09:45:23 PM│ 08:45:23 PM  │         │
│  └─────────────┴─────────────┴─────────────┘         │
│                                                      │
│  Peak: 8 AM – 2 PM ET weekdays                       │
│  Weekends: off-peak all day                          │
└──────────────────────────────────────────────────────┘
```

**Detalhes visuais:**

1. **Status banner:** 
   - ON-PEAK: texto em `SCARLET` (#FF2020), bold, grande (20px+)
   - OFF-PEAK: texto em `TEXT_PRIMARY` (#F0F0F5), bold, grande
   - Weekend: "OFF-PEAK — Weekend" 

2. **Countdown (relógio grande):**
   - Formato `HH:MM:SS`, font-size ~36px, font-weight bold, monospace
   - Cor: `CRIMSON` quando on-peak (contando pra acabar), `TEXT_SECONDARY` quando off-peak (contando pro próximo pico)
   - Label dinâmico acima:
     - Se on-peak: "Off-peak starts in:"
     - Se off-peak weekday: "Peak starts in:" 
     - Se off-peak weekend: "Peak starts in:" (conta até segunda 8AM ET)
   - Atualizar a cada 1 segundo via `QTimer`

3. **Barras de timeline (2 barras, uma por fuso):**
   - Barra horizontal representando 24h (0h às 0h)
   - Região de pico preenchida em `CRIMSON` com opacity ~60%
   - Região off-peak em `BG_SURFACE`
   - Marcador "now" (cursor/indicator): linha vertical branca fina na posição correspondente à hora atual naquele fuso
   - Labels de hora nas extremidades e no início/fim do pico
   - Barra ET: pico marcado de 8AM a 2PM
   - Barra BRT: pico marcado de 9AM a 3PM (offset de +1h em relação a ET normalmente, mas calculado dinamicamente pelo fuso real)
   - Altura de cada barra: ~20px + labels

4. **Cards de timezone (3 cards em row):**
   - LOCAL ZONE: nome do timezone local (ex: "America/Sao_Paulo")
   - LOCAL TIME: hora atual local, formato HH:MM:SS, atualiza 1/s
   - EASTERN TIME: hora atual ET, formato HH:MM:SS, atualiza 1/s
   - Estilo: fundo `BG_SURFACE`, borda `BORDER_DEFAULT`, label `TEXT_MUTED`, valor `TEXT_PRIMARY`

5. **Footer info:** Texto explicativo fixo em `TEXT_MUTED`, font 11px:
   - "Peak: 8 AM – 2 PM ET on weekdays"
   - "Weekends: off-peak all day"

**Implementação técnica:**
- Novo arquivo: `ui/peak_monitor.py`
- Classe `PeakMonitorWidget(QWidget)` 
- Timer interno de 1 segundo para atualizar countdown + cursores das barras + relógios
- As barras podem ser pintadas com `QPainter` em `paintEvent` ou ser widgets customizados
- Cálculo de peak status: pegar hora atual em ET, checar se é weekday e se está entre 8:00 e 14:00
- Cálculo do countdown: se on-peak, delta até 14:00 ET do mesmo dia. Se off-peak weekday, delta até 8:00 ET do próximo dia útil. Se off-peak weekend, delta até 8:00 ET de segunda.

#### Footer
- Status text: "Updated Xm ago" / "Cached — updated Xh ago"
- Botão refresh (↻)

### 4.5 Tab: Sessions (REDESIGN + FEATURES NOVAS)

#### Seção: Data Cards (topo)
- 3 cards em row:
  - **Tokens Today**: valor em `CRIMSON`, subtítulo com breakdown
  - **Active Sessions**: contagem, dot `STATUS_ACTIVE`
  - **This Week**: total de sessões da semana

#### Seção: Model Breakdown (NOVA)
- Barra horizontal empilhada mostrando proporção de uso por modelo
  - Cada modelo tem uma cor diferente (tons de vermelho/carmesim/amber)
  - Legenda abaixo: modelo → tokens in/out
- Dados: agregar `token_usage` de todas as sessões do dia

#### Seção: Session List
- Manter expand/collapse por sessão
- Melhorar layout do item:
  - Linha 1: título (bold) + tokens (accent color) alinhado à direita
  - Linha 2: projeto · duração · msgs · tempo relativo
  - Indicador de ativo: dot `STATUS_ACTIVE` (branco, NÃO verde)
- Expanded: model breakdown, custo, entrypoint, branch
- Scrollable, max 250px

#### Seção: Peak Hours (NOVA)
- Heatmap simples (24 colunas = horas do dia)
- Colorir cada hora com intensidade baseada em quantas mensagens/tokens foram usados naquela hora
- Dados: calcular a partir de `data_store.get_sessions_since()` agrupando por hora do dia
- Labels: "12a, 6a, 12p, 6p, 12a" nas extremidades
- Altura: ~40px, compacto

### 4.6 Tab: Processes

- Listar processos Claude encontrados por `find_claude_processes()`
- Layout por processo:
  - Dot de status (branco = running)
  - Nome/PID
  - Memória (MB)
  - Uptime
  - Working directory (truncado)
  - Botão ✕ para terminar (com confirmação)
- Botão "End All" em `SCARLET` no topo
- Botão refresh (↻)
- Se nenhum processo: mensagem centralizada "No Claude processes running"

### 4.7 Tab: Config

- Manter a mesma funcionalidade da SettingsTab atual
- Melhorar visual para combinar com o novo design:
  - Inputs com estilo consistente (fundo `BG_SURFACE`, borda `BORDER_DEFAULT`)
  - Labels em `TEXT_SECONDARY`
  - Section headers em `TEXT_PRIMARY` com font-weight bold
  - Toggle switches ao invés de checkboxes onde possível

---

## 5. ESTILO QSS GLOBAL

Atualizar `ui/styles.py` com a nova paleta e um QSS global mais polido:

- Font family: "Segoe UI", "Inter", sans-serif
- Font size padrão: 13px
- Scrollbars: 6px, handle com border-radius, cores da paleta
- Tooltips: fundo `BG_OVERLAY`, texto `TEXT_PRIMARY`, borda `BORDER_DEFAULT`
- Botões: transição suave de cor no hover
- Inputs (QSpinBox, QCheckBox): estilizados consistentemente

---

## 6. TRAY ICON (em `app.py`)

Atualizar `_make_icon()`:
- Remover a stripe azul (`ROYAL_BLUE`) — usar `CRIMSON` como accent
- Background dinâmico:
  - `BG_ELEVATED` quando utilização < 70% (neutro)
  - `WARNING_AMBER` quando 70-90%
  - `SCARLET` quando ≥ 90%
- Letra "R" (de RIAS) ao invés de "C"

---

## 7. REGRAS TÉCNICAS

1. **Framework:** PySide6 (>=6.8, <6.9). Não introduzir dependências novas.
2. **Não alterar arquivos backend** — apenas `ui/`, referências visuais em `app.py`, e `ui/styles.py`.
3. **Manter todas as conexões de Signal/Slot** — a interface entre backend e UI (signals como `usage_updated`, `error_occurred`, `auth_missing`, `scan_completed`, `settings_changed`) deve continuar funcionando.
4. **Manter a hotkey** Ctrl+Shift+C para toggle do popup.
5. **Manter exports** CSV/JSON na aba de Sessions.
6. **Manter o click-outside-to-close** e posicionamento near-tray.
7. **Código em inglês** (variáveis, nomes, docstrings), comentários podem ser em inglês.
8. **Código limpo:** type hints, docstrings, separação de responsabilidades.
9. **Testar** que o app ainda abre e funciona após cada mudança significativa.
10. **Animações:** usar `QPropertyAnimation` para transições suaves onde indicado. Não exagerar — manter performance.

---

## 8. ORDEM DE EXECUÇÃO SUGERIDA

0. **OBRIGATÓRIO:** Localizar e ler o skill `ui-ux-pro-max` (ver seção 0)
1. Atualizar `ui/styles.py` com a nova paleta completa + QSS global
2. Atualizar `ui/tab_bar.py` com o novo estilo (underline animada)
3. Redesign do `ui/popup_window.py`:
   - Expandir para 560px
   - Novo header com badge e indicador live
   - 4 tabs (Dashboard, Sessions, Processes, Config)
   - Fade-in animation
4. Redesign do `ui/trend_chart.py` com as novas cores
5. Redesign do `ui/data_cards.py` com o novo visual
6. Redesign do `ui/session_list.py` com indicadores brancos
7. Implementar **Today's Usage** section (nova)
8. Implementar **Peak Monitor** — `ui/peak_monitor.py` (novo arquivo)
   - Status banner + countdown grande + barras ET/BRT + cards timezone
9. Implementar **Model Breakdown** section (nova)
10. Implementar **Peak Hours heatmap** (nova)
11. Redesign do `ui/settings_tab.py`
12. Atualizar tray icon em `app.py`
13. Teste final completo

---

## 9. RESUMO

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Largura | 420px | 560px |
| Tabs | 3 (Usage, Sessions, Config) | 4 (Dashboard, Sessions, Processes, Config) |
| Cor primária | Crimson #B90E0A + Royal Blue #5B6FE8 | Crimson #DC143C (sem azul) |
| Sessão ativa | Dot verde | Dot branco |
| Today's Usage | Não existia | Card com breakdown completo |
| Model Breakdown | Não existia | Barra empilhada + lista |
| Peak Hours | Não existia | Heatmap 24h |
| Peak Monitor | Não existia | Status on/off-peak + countdown + barras ET/BRT |
| Tray icon | Letra "C" com stripe azul | Letra "R" em carmesim |
| Trend chart | 2 cores (crimson + blue) | 2 tons de vermelho (crimson + ember) |

---

## 10. PROGRESSO DO REDESIGN

| # | Etapa | Arquivo(s) | Status |
|---|-------|-----------|--------|
| 0 | Localizar e ler o skill `ui-ux-pro-max` | — | ✅ Concluído |
| 1 | Atualizar paleta completa + QSS global | `ui/styles.py` | ✅ Concluído |
| 2 | Tab bar com underline animada | `ui/tab_bar.py` | ✅ Concluído |
| 3 | Redesign da janela principal (560px, header, 4 tabs, fade-in) | `ui/popup_window.py` | ✅ Concluído |
| 4 | Trend chart com novas cores (CRIMSON_LIGHT + EMBER) | `ui/trend_chart.py` | ✅ Concluído |
| 5 | Data cards com STATUS_ACTIVE branco e BORDER_ACCENT | `ui/data_cards.py` | ✅ Concluído |
| 6 | Session list com dots brancos e EMBER para modelos | `ui/session_list.py` | ✅ Concluído |
| 7 | Today's Usage section (tokens do dia + breakdown 2x2) | `ui/popup_window.py` | ✅ Concluído |
| 8 | Peak Monitor (status + countdown + barras ET/BRT + cards tz) | `ui/peak_monitor.py` | ✅ Concluído |
| 8a | Corrigir dependência `zoneinfo` no Windows (DST manual) | `ui/peak_monitor.py` | ✅ Concluído |
| 9 | Model Breakdown section (barra empilhada + legenda) | `ui/popup_window.py` | ✅ Concluído |
| 10 | Peak Hours heatmap 24h na aba Sessions | `ui/popup_window.py` | ✅ Concluído |
| 11 | Redesign da aba Config | `ui/settings_tab.py` | ✅ Concluído |
| 12 | Tray icon: letra "R", paleta RIAS, sem azul | `app.py` | ✅ Concluído |
| 13 | Correção: popup invisível (GC da QPropertyAnimation) | `ui/popup_window.py` | ✅ Concluído |
| 14 | Hotkey: fallback para Ctrl+Shift+M / Ctrl+Alt+M | `hotkey.py`, `app.py` | ✅ Concluído |
| 15 | Correção: `QPen` não importado em popup_window.py | `ui/popup_window.py` | ✅ Concluído |
