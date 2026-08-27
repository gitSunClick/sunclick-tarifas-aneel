# Automação de tarifas ANEEL → Google Sheets

Continuação do handoff de 26/08/2026 (`Handoff_Automacao_Tarifas_ANEEL.docx`).
Esta é a "versão limpa" recomendada na seção 15 do handoff — baixa a base
oficial da ANEEL (CSV) em vez de depender do relatório Power BI (a tentativa
com a API interna do Power BI deu HTTP 401 e foi abandonada; a API
`datastore_search_sql` do CKAN deu HTTP 400 e também foi abandonada — ver
handoff, seções 6 a 9).

## Como o problema foi resolvido

Duas fontes oficiais e estáveis (Dados Abertos da ANEEL, formato CSV):

1. **`tarifas-homologadas-distribuidoras-energia-eletrica.csv`** — TUSD e
   TE por distribuidora/subgrupo/modalidade/classe, com vigência. Usada
   para TUSD/TE (B1 + Convencional + Residencial) e TUSD G (A2 + Geração).
   https://dadosabertos.aneel.gov.br/dataset/tarifas-distribuidoras-energia-eletrica

2. **`componentes-tarifarias-{ano}.csv`** — formato "longo" (uma linha por
   componente tarifário), usada para **Fio B**.
   https://dadosabertos.aneel.gov.br/dataset/componentes-tarifarias

As URLs exatas (incluindo os `resource_id`) já estão em `config.py`.

> **ICMS, PIS e COFINS ficaram de fora da extração automática.**
> Confirmei em 26/08/2026 (contra o CSV real de 246MB, e buscando o
> portal inteiro) que a ANEEL não publica esses 3 valores em nenhum
> dataset de Dados Abertos — faz sentido, ICMS é imposto estadual (cada
> estado publica o seu) e PIS/COFINS federal não é um "componente
> tarifário" da distribuidora do mesmo jeito que TUSD/TE/Fio B são. O
> script não toca nessas 3 colunas na planilha (não apaga, não sobrescreve
> — só ignora). Se vocês tiverem outra fonte pra elas (tabela interna,
> SEFAZ de cada estado), dá pra adicionar como uma etapa separada depois.

> Confirmei a existência e as colunas dessas duas fontes (dicionários de
> dados oficiais da ANEEL), mas os arquivos são grandes demais (o de
> tarifas homologadas passa de 30 MB) para eu ter conseguido abrir e
> conferir linha a linha durante esta conversa. A lógica de filtro/vigência
> foi testada com dados sintéticos que reproduzem o schema oficial
> (`teste_smoke.py`, incluso) — mas os valores REAIS (SigAgente de cada
> distribuidora, e se o valor de controle da CEEE-RS bate) só são
> confirmados rodando os scripts abaixo com internet de verdade.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `config.py` | Toda a configuração: URLs da ANEEL, filtros tarifários, lista das 31 distribuidoras (com `sig_agente` a preencher), mapeamento de colunas da planilha. |
| `aneel_lib.py` | Download com cache + lógica de busca do registro vigente (trata ambiguidade, vigência, normalização). |
| `descobrir_sigagente.py` | Passo 1: descobre os códigos `SigAgente` reais da ANEEL e sugere o DE/PARA para as 31 distribuidoras. |
| `validar_controle.py` | Passo 2: confere se a extração da CEEE-RS bate com o valor visto no portal (TUSD 478,63 / TE 343,37). |
| `atualizar_google_sheets.py` | Passo 3: extrai as 31 distribuidoras e atualiza o Google Sheets (com `DRY_RUN` por padrão). |
| `teste_smoke.py` | Testes de lógica com dados sintéticos (não usa internet). |

## Passo a passo

### 0. Instalar dependências

```bash
pip install -r requirements.txt
```

### 1. Descobrir os códigos SigAgente reais

```bash
python descobrir_sigagente.py
```

Isso baixa a base oficial (pode demorar — arquivo grande) e sugere, por
similaridade de texto, qual `SigAgente` da ANEEL corresponde a cada uma das
31 distribuidoras do `config.py`. **Confira cada sugestão manualmente**
antes de colar em `config.py` — nomes de distribuidoras mudam (fusões,
trocas de grupo), então a sugestão automática pode errar. Se quiser ver
todos os valores possíveis: `python descobrir_sigagente.py --listar-tudo`.

Faça o mesmo para os componentes tarifários, para confirmar a grafia exata
de ICMS/PIS/COFINS/Fio B na base:

```bash
python descobrir_sigagente.py --componentes
```

Ajuste `config.COMPONENTES_DESEJADOS` se a grafia real for diferente do
que já deixei configurado.

### 2. Validar contra o valor de controle

Depois de preencher pelo menos o `sig_agente` da CEEE-RS em `config.py`:

```bash
python validar_controle.py
```

Só continue para o próximo passo se aparecer **"PASSOU"**. Se falhar,
pare e investigue antes de tocar nas outras 30 distribuidoras — é
exatamente o que o handoff pede na seção 15.3.

### 3. Rodar em DRY RUN (sempre primeiro)

```bash
export GOOGLE_SHEET_ID="cole_o_id_da_planilha_aqui"
export GOOGLE_WORKSHEET="nome_exato_da_aba"
export GOOGLE_SERVICE_ACCOUNT_FILE="/caminho/para/service_account.json"
DRY_RUN=true python atualizar_google_sheets.py
```

Isso imprime, para cada uma das 31 distribuidoras, o status (`OK`,
`SEM_TARIFA_VIGENTE`, `AMBIGUO`, `SIGLA_NAO_MAPEADA`) e os valores que
seriam gravados — **sem escrever nada na planilha ainda**. Confira o
preview com calma antes de seguir.

### 4. Gravar de verdade

Só depois do preview conferido:

```bash
DRY_RUN=false python atualizar_google_sheets.py
```

O script pede confirmação (`digite SIM`) antes de gravar. Ele atualiza
célula por célula, casando pela coluna-chave (`config.COLUNA_CHAVE_PLANILHA`)
e pelo nome exato de cada coluna (`config.COLUNAS_PLANILHA`) — **não recria
nem limpa a planilha inteira**, e nunca apaga um valor existente quando uma
distribuidora está com status de pendência (só grava a observação na
coluna de status).

> **Confira `config.COLUNA_CHAVE_PLANILHA` e `config.COLUNAS_PLANILHA`
> contra o cabeçalho real da sua planilha antes do passo 4** — não tive
> acesso à planilha para confirmar os nomes exatos das colunas, então
> deixei valores de partida baseados na tabela descrita no handoff
> (seção 2). O gspread só encontra a coluna se o texto do cabeçalho for
> idêntico.

## Credenciais do Google (Service Account)

Igual ao que já foi decidido no handoff (seção 11) — conta de serviço, não
login pessoal:

1. [console.cloud.google.com](https://console.cloud.google.com/) → criar/
   escolher um projeto.
2. **APIs e serviços → Biblioteca** → ativar **Google Sheets API**.
3. **APIs e serviços → Credenciais → Criar credenciais → Conta de
   serviço** (ex.: `aneel-tarifas-bot`).
4. Na conta de serviço criada → **Chaves → Adicionar chave → Criar nova
   chave → JSON** → baixa o `service_account.json`.
5. Abra sua planilha do Google Sheets → **Compartilhar** → cole o e-mail
   da conta de serviço (algo como
   `aneel-tarifas-bot@seu-projeto.iam.gserviceaccount.com`) como **Editor**.
6. Copie o ID da planilha (entre `/d/` e `/edit` na URL).

**Nunca** suba `service_account.json` para um repositório, chat ou
documento (handoff, seções 12 e 17) — o `.gitignore` incluso já bloqueia
isso, `*.har` também (arquivos de captura de rede podem conter sessão/
cookies).

## Agendamento (recorrente)

Duas opções — escolha a que fizer mais sentido:

### Opção A — cron na sua máquina/servidor

```
0 8 * * * cd /caminho/para/aneel_tarifas && DRY_RUN=false /usr/bin/python3 atualizar_google_sheets.py <<< SIM >> log.txt 2>&1
```

### Opção B — GitHub Actions

O arquivo `.github/workflows/atualizar_tarifas.yml` já vem pronto (roda
todo dia às 08h de Brasília). Para usar:

1. Suba esta pasta para um repositório (pode ser privado). O `.gitignore`
   já impede subir credenciais/cache.
2. Em **Settings → Secrets and variables → Actions**, crie os *secrets*:
   `GOOGLE_SERVICE_ACCOUNT_JSON` (conteúdo inteiro do JSON) e
   `GOOGLE_SHEET_ID`.
3. Em **Variables**, crie `GOOGLE_WORKSHEET` com o nome exato da aba.
4. O workflow roda sempre em DRY_RUN primeiro e só grava de verdade se o
   preview não falhar — ajuste esse comportamento no `.yml` conforme sua
   confiança na automação for aumentando.

> Sites do governo às vezes bloqueiam acesso vindo de servidores de nuvem.
> Se o GitHub Actions não conseguir baixar os arquivos da ANEEL, use a
> Opção A a partir de uma rede "normal".

## Proteções já implementadas (handoff, seção 12)

- Nunca apaga valores existentes quando não há tarifa vigente válida —
  só grava o status/observação.
- Nunca escolhe sozinho entre registros ambíguos — reporta `AMBIGUO` e
  não grava nada de tarifa para aquela distribuidora.
- Atualiza por nome de coluna, não por posição fixa.
- Roda em `DRY_RUN` por padrão, com preview antes de qualquer escrita.
- Guarda internamente `DatFimVigencia`, pronto para a próxima execução
  detectar quando a vigência de uma distribuidora expirar.
- `.gitignore` cobre `service_account.json`, `credentials.json`, `*.har`
  e o cache de downloads.

## O que ainda falta (não dá para eu resolver sem rodar contra dados reais)

1. Confirmar os 31 `SigAgente` em `config.py` (`descobrir_sigagente.py`).
2. Confirmar que `validar_controle.py` passa para a CEEE-RS.
3. Confirmar a grafia real de ICMS/PIS/COFINS/Fio B em
   `DscComponenteTarifario` (`descobrir_sigagente.py --componentes`).
4. Confirmar `COLUNA_CHAVE_PLANILHA` e `COLUNAS_PLANILHA` contra o
   cabeçalho real da sua planilha do Google Sheets.
