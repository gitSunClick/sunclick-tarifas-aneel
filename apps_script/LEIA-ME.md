# Escrever na planilha via Apps Script (sem Google Cloud)

Esse método evita completamente o Google Cloud Console e a política
`iam.disableServiceAccountKeyCreation` que bloqueou a criação da chave de
service account. Em vez de o script Python falar diretamente com a API do
Google Sheets, ele manda os dados por HTTP para um pequeno script do Google
Apps Script que roda **vinculado à própria planilha**, com a sua própria
autorização.

## Passo a passo

1. Abra a planilha `TARIFAS_SUNCLICK` no navegador.
2. Menu **Extensões > Apps Script**. Isso abre o editor num projeto já
   vinculado a essa planilha.
3. Apague todo o conteúdo do arquivo `Code.gs` que abrir por padrão.
4. Abra o arquivo `Code.gs` que eu te mandei (nesta mesma pasta
   `apps_script/`), copie o conteúdo inteiro e cole no editor do Apps
   Script, substituindo tudo.
5. Na primeira linha de código (`var TOKEN_ESPERADO = ...`), troque o texto
   `"TROQUE_ISTO_POR_UM_TOKEN_SECRETO_SEU"` por uma senha/token qualquer,
   só sua — pode ser uma frase aleatória, tipo
   `"sunclick-tarifas-8f2a91"`. Guarde esse valor, você vai usar no passo 9.
6. Salve o projeto (ícone de disquete, ou Ctrl+S). Pode dar o nome que
   quiser ao projeto, ex. "Atualizador de Tarifas".
7. No canto superior direito, clique em **Implantar > Nova implantação**.
   - Clique no ícone de engrenagem ao lado de "Selecionar tipo" e escolha
     **Aplicativo da Web**.
   - Em "Executar como", deixe **Eu (seu e-mail)**.
   - Em "Quem pode acessar", escolha **Qualquer pessoa**.
   - Clique em **Implantar**.
8. O Google vai pedir autorização — é o SEU script pedindo permissão pra
   editar a SUA planilha, sob a SUA conta. Clique em **Autorizar acesso**,
   escolha sua conta, e se aparecer uma tela de aviso "app não verificado"
   clique em **Avançado > Acessar (nome do projeto), não seguro** — é
   esperado para scripts pessoais não publicados na Play Store, não tem
   risco porque o código é o que você acabou de colar.
9. Depois de autorizar, aparece uma URL parecida com:
   `https://script.google.com/macros/s/AKfycb.../exec`
   Copie essa URL inteira.

## Onde usar isso no script Python

No PowerShell, antes de rodar `atualizar_google_sheets.py`, defina:

```powershell
$env:GOOGLE_APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycb.../exec"
$env:GOOGLE_APPS_SCRIPT_TOKEN = "sunclick-tarifas-8f2a91"   # o mesmo token do passo 5
$env:GOOGLE_WORKSHEET = "TARIFAS_SUNCLICK"                  # nome exato da aba
```

Com `GOOGLE_APPS_SCRIPT_URL` definida, o script **ignora** `GOOGLE_SHEET_ID`
e qualquer credencial de service account/OAuth — ele nem tenta usar o
gspread, só faz um POST no seu Web App. Não precisa mais criar nada no
Google Cloud Console.

Rode normalmente:

```powershell
$env:DRY_RUN = "true"
python atualizar_google_sheets.py
```

O preview no terminal continua funcionando igual (é gerado localmente,
antes de qualquer chamada ao Apps Script). Só quando você rodar com
`DRY_RUN=false` e confirmar com `SIM` é que o Python chama o Web App, que
aí sim escreve na planilha.

## Se precisar mudar o Code.gs depois

Sempre que editar o `Code.gs` no editor do Apps Script (por exemplo pra
trocar o token), você precisa **implantar de novo**:
**Implantar > Gerenciar implantações > ícone de lápis na implantação
existente > Nova versão > Implantar**. Só salvar o arquivo não é
suficiente — o Web App continua rodando a versão implantada anteriormente
até você reimplantar.

## Segurança

O Web App fica acessível a "qualquer pessoa" com a URL — mas a URL é longa
e aleatória (não é adivinhável), e o `Code.gs` confere o token antes de
escrever qualquer coisa. Ainda assim, trate a URL e o token como segredos:
não cole em lugares públicos, e se desconfiar que vazou, gere um token novo
no `Code.gs` e reimplante.
