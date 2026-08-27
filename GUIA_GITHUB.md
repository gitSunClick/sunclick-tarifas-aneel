# Guia: criar conta e repositório no GitHub, do zero

Esse guia coloca o script Python rodando sozinho todo dia, sem depender do
seu computador. O GitHub roda o script na nuvem deles, num horário
agendado, e ele escreve na planilha pelo mesmo Web App do Apps Script que
já configuramos (a mesma URL e token de antes — não precisa mexer nisso de
novo).

## 1. Criar a conta

1. Acesse **github.com** e clique em **Sign up**.
2. Use um e-mail seu (pode ser o corporativo, `nathalia@sunclick.com.br`,
   ou um pessoal — não muda nada tecnicamente; é só a identidade da conta
   que vai possuir o repositório).
3. Escolha um nome de usuário. Como é uma conta "profissional" que vai
   guardar automações da Sunclick, algo neutro tipo `sunclick-energia` ou
   `nathalia-sunclick` funciona bem.
4. Confirme o e-mail (o GitHub manda um código).
5. Na tela de perguntas iniciais ("What are you here to do?"), pode pular
   ou escolher qualquer opção — não afeta nada do que vamos fazer.
6. O plano **gratuito (Free)** já é suficiente pra tudo isso — repositório
   privado, GitHub Actions com minutos grátis por mês, sem custo.

## 2. Criar o repositório

1. Clique no `+` no canto superior direito > **New repository**.
2. Nome: algo como `sunclick-tarifas-aneel`.
3. Marque **Private** (importante — mantém o código e a configuração
   fora de busca pública).
4. NÃO marque "Add a README file" (vamos subir os arquivos já prontos).
5. Clique em **Create repository**.

## 3. Subir os arquivos

Você vai receber de mim um arquivo `.zip` com todo o projeto. Depois de
baixar e descompactar no seu computador:

1. Na página do repositório recém-criado, procure o link
   **"uploading an existing file"** (aparece no meio da página inicial,
   em "Quick setup").
2. Abra a pasta descompactada no Explorador de Arquivos do Windows,
   selecione **todos os arquivos e pastas** dentro dela (Ctrl+A) e
   **arraste tudo** pra dentro da página do navegador, na área de
   upload.
   - Importante: arraste o **conteúdo** da pasta (os arquivos), não a
     pasta em si — senão tudo fica um nível mais fundo do que deveria.
   - O GitHub preserva a estrutura de subpastas (`.github/workflows/`,
     `apps_script/`) automaticamente ao arrastar.
3. Espere o upload terminar (a lista de arquivos aparece na tela).
4. Desça até o final da página, escreva uma mensagem tipo "primeira
   versão" no campo de commit, e clique em **Commit changes**.

## 4. Guardar a URL e o token do Apps Script como segredo

Isso evita que a URL e o token fiquem visíveis no código.

1. No repositório, vá em **Settings** (aba no topo) > no menu lateral
   esquerdo, **Secrets and variables > Actions**.
2. Clique em **New repository secret**.
   - Nome: `GOOGLE_APPS_SCRIPT_URL`
   - Valor: cole a URL do Web App (termina em `/exec`)
   - Clique em **Add secret**.
3. Repita pra um segundo segredo:
   - Nome: `GOOGLE_APPS_SCRIPT_TOKEN`
   - Valor: o token que você definiu no `Code.gs`
   - **Add secret**.

## 5. Testar manualmente antes de confiar no agendamento

1. Vá na aba **Actions** do repositório.
2. Se aparecer um aviso pra habilitar workflows, clique em **"I understand
   my workflows, go ahead and enable them"**.
3. Clique no workflow **"Atualizar tarifas ANEEL no Google Sheets"** na
   lista à esquerda.
4. Clique em **Run workflow** (botão à direita) > **Run workflow** de
   novo pra confirmar.
5. Acompanhe a execução clicando nela assim que aparecer na lista —
   você vê o mesmo tipo de log que via no seu PowerShell, agora rodando
   na nuvem do GitHub.
6. Se os dois passos (dry run e escrita real) terminarem com ✅ verde,
   confere a planilha — deve ter atualizado igual ao teste manual que já
   fizemos.

## 6. Daqui pra frente

Com isso funcionando, o workflow roda **sozinho, todo dia às 08:00
(horário de Brasília)**, sem precisar de nada seu. Pra mudar o horário,
me avisa o horário desejado que eu ajusto a linha `cron` do arquivo
`.github/workflows/atualizar_tarifas.yml`.

Se algum dia quiser rodar fora do horário programado, é só repetir o
passo 5 (Actions > Run workflow) a qualquer momento.

## Se algo der errado

Cada execução fica registrada na aba Actions com log completo — se o
workflow falhar (❌ vermelho), me manda o log de erro (tem um botão de
"download log" ou você pode copiar o texto da tela) que eu identifico o
problema. Erros mais prováveis: token/URL do Apps Script errados nos
secrets, ou a aba `TARIFAS_SUNCLICK` foi renomeada na planilha.
